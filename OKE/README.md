# OCI Kubernetes Engine (OKE) Hands-on Lab

**Project:** OCITestDriveBudapest

## Goal / Estimated Time for the Hands-on Lab

Create an OKE cluster in the existing `p01-vcn` with a public Kubernetes API endpoint and three private managed worker nodes. Use either the OCI Console or Terraform, then connect with `kubectl` and verify that all workers are ready.

**Estimated time:** 45–60 minutes, including provisioning. This lab creates billable compute and boot volumes. It reuses the network from the network lab.

## Contents

- [Before you begin](#before-you-begin)
- [Target configuration](#target-configuration)
- [Option A - Deployment steps for OCI Console](#option-a---deployment-steps-for-oci-console)
- [Option B - Deployment steps for Terraform](#option-b---deployment-steps-for-terraform)
- [Troubleshooting](#troubleshooting)
- [Optional cleanup](#optional-cleanup)
- [Oracle documentation references](#oracle-documentation-references)

Choose one deployment option per cluster. Do not deploy both options with the same names.

## Before you begin

1. Sign in to OCI and select **Germany Central (Frankfurt)** (`eu-frankfurt-1`).
2. Complete the compartment and network labs. Record the resource compartment OCID and network compartment OCID (they may be identical).
3. Have permissions to manage OKE clusters/node pools, compute instances, VNICs, volumes and NSGs, and to use the existing VCN/subnets and gateways. Ask the instructor to verify IAM using Oracle's OKE policy reference below. Cluster access also requires OCI authentication and Kubernetes authorization.
4. Check available quotas/capacity for **6 E5 OCPUs, 24 GB RAM and three worker boot volumes** in AD-3. The availability domain prefix `sgUC` is tenancy-specific; replace it when needed.
5. Verify that `p01-subnet-public-lb` is regional and public, and `p01-subnet-private-vm` is private and regional (or AD-3-specific). Leave sufficient free IP addresses for the endpoint, nodes and future load balancers.
6. Check network routing and DNS:
   - Public subnet: `0.0.0.0/0` to an Internet Gateway.
   - Private workers: `0.0.0.0/0` to a NAT Gateway for image pulls and other internet access.
   - Private workers: the regional **All <region> Services in Oracle Services Network** service CIDR to a Service Gateway. The gateway must support that service label.
   - VCN DNS resolution enabled, using Internet and VCN Resolver DHCP options.
7. Identify the public IPv4 egress address used by your laptop/VPN and record it as a `/32` CIDR. Use the address seen by OCI after NAT/VPN, not your laptop's private address.
8. For command-line steps, install/configure OCI CLI and `kubectl` compatible with the selected server version. For Terraform, install Terraform 1.5 or later (below 2.0), and configure OCI API key authentication in `~/.oci/config`. Never commit a private key, credentials, kubeconfig or Terraform state.

### Confirm versions and images first

The requested default is **`v1.37`**. Oracle's supported-version page currently lists **1.37.0 as preview**, while its OL8 worker image catalog also lists **1.37.1** builds. These published sources do not establish which combination your region currently offers. Query OKE in your tenancy before provisioning. This lab preserves your requested minor version and image build; it does not silently select a different version/date. A minor version selects the patch offered by OKE, so record the actual patch after deployment.

Run in OCI Cloud Shell or your configured terminal (set your own OCID):

```bash
export OCI_CLI_REGION=eu-frankfurt-1
export LAB_COMPARTMENT_OCID='ocid1.compartment.oc1..REPLACE_ME'

oci ce cluster-options get --cluster-option-id all \
  --should-list-all-patch-versions false \
  --query 'data."kubernetes-versions"' --output json

oci ce node-pool-options get --node-pool-option-id all \
  --compartment-id "$LAB_COMPARTMENT_OCID" \
  --node-pool-k8s-version v1.37 --output json

oci iam availability-domain list --compartment-id "$LAB_COMPARTMENT_OCID" \
  --query 'data[].name' --output table
```

Inspect `kubernetes-versions`, `shapes` and `sources` in the node pool response. If your installed CLI does not recognize the version filter, update it or omit that flag and inspect the returned sources. To inspect exact patches, repeat the cluster-options command with `--should-list-all-patch-versions true`.

Look for a **standard x86 Oracle Linux 8 OKE worker image** containing build **`2026.10.16-0`** and the selected Kubernetes version. Exclude `aarch64` and GPU images for this E5 CPU shape. The catalog lists `Oracle-Linux-8.10-2026.10.16-0-OKE-1.37.1-2067`; treat it as a candidate, not proof of regional availability. Record the exact image name and regional OCID from OKE's response. The date is part of the underlying image build name; it is not necessarily the OKE image publication date.

If the requested combination is unavailable, stop and agree on an available version/image combination with the instructor, then update the Console choices or parameter file. Preview versions are for testing and have limited support.

## Target configuration

| Setting | Default |
| --- | --- |
| Region | `eu-frankfurt-1` |
| Cluster / node pool | `p01-oke` / `p01-oke-pool-01` |
| Cluster type | Basic, managed nodes |
| Kubernetes version, control plane and workers | `v1.37`; actual patch subject to OKE availability |
| Pod networking | Flannel overlay (`FLANNEL_OVERLAY`) |
| VCN | Existing `p01-vcn` (`10.0.0.0/16` in the network lab) |
| Kubernetes API endpoint subnet | `p01-subnet-public-lb` (`10.0.0.0/24`) |
| Assign public IP to API endpoint | Yes |
| Default Service load balancer subnet | `p01-subnet-public-lb` |
| Worker subnet | `p01-subnet-private-vm` (`10.0.1.0/24`) |
| Worker placement | `sgUC:EU-FRANKFURT-1-AD-3` |
| Worker shape | `VM.Standard.E5.Flex` |
| Per-worker resources | 2 OCPUs, 8 GB RAM |
| Worker image | OKE Worker Node Images, Oracle Linux 8, build `2026.10.16-0` |
| Worker count | 3; all in the specified AD |
| Pod CIDR / service CIDR | `10.244.0.0/16` / `10.96.0.0/16` |
| Instance metadata | IMDSv2; legacy IMDSv1 disabled |
| API client access | TCP 6443 from your specified egress CIDR(s) |

The two Kubernetes CIDRs must not overlap each other, the VCN, or connected networks. No pod subnet is required for Flannel. All workers in one AD is a lab choice and does not provide availability across ADs.

Selecting a load balancer subnet **does not create a load balancer**. OKE can create one later for a Kubernetes Service of type `LoadBalancer`; it does not reuse the standalone load balancer from the earlier lab.

### Network security used by both options

Create two NSGs in `p01-vcn`, named `p01-oke-api-nsg` and `p01-oke-worker-nsg`. Terraform creates these automatically. For Console deployment, create them before the cluster using **Networking → Virtual cloud networks → p01-vcn → Network security groups → Create**.

Add these **stateful** rules (source ports are All):

| NSG | Direction | Source / destination | Protocol / destination port | Purpose |
| --- | --- | --- | --- | --- |
| API | Ingress | Your public client CIDR(s) | TCP 6443 | kubectl access |
| API | Ingress | Worker NSG | TCP 6443 | Workers to API |
| API | Ingress | Worker NSG | TCP 12250 | Workers to OKE control plane |
| API | Ingress | Worker subnet CIDR | ICMP type 3, code 4 | Path MTU discovery |
| Worker | Ingress | Worker NSG itself | All protocols | Flannel and worker/pod communication |
| Worker | Ingress | API NSG | All TCP ports | Control plane to workers |
| Worker | Ingress | API subnet CIDR | ICMP type 3, code 4 | Path MTU discovery |
| Both | Egress | `0.0.0.0/0` | All protocols | Lab outbound access through existing routes |

Use the actual subnet CIDRs if you changed the network lab. These are IPv4 lab rules; the broad outbound rule simplifies access to OKE services, registries and repositories. Review subnet security lists too: OCI combines their allows with NSG allows, so a broad existing 6443 rule can defeat the intended client restriction. Terraform does not edit existing security lists or routes. Retain required network-lab rules for other resources.

No load balancer ingress or NodePort rules are needed for this lab's readiness check. Before creating a Service load balancer, configure its listener access and LB-to-worker backend/health-check rules according to the service and Oracle's network reference. OKE's security-list automation, if enabled for that Service, may modify shared subnet lists.

## Option A - Deployment steps for OCI Console

### 1. Prepare the network

1. Open `p01-vcn` and check the subnets, routes, gateways and DNS described above.
2. Create and populate the two NSGs using the security table. Creating both NSGs first lets you select them as rule sources.
3. Confirm the version/image combination is available. Keep the compartment and image details ready.

### 2. Start Custom Create

1. Open **Developer Services → Kubernetes Clusters (OKE)** (the service may appear as **Kubernetes Engine**).
2. Select your lab compartment and choose **Create cluster**.
3. Select **Custom create** to use the existing network, then begin the workflow.
4. Set the name to `p01-oke` and choose the lab compartment.
5. Select Kubernetes **1.37**. To pin a patch, show patch versions and choose one verified earlier. If unavailable, use the agreed replacement in both cluster and pool.
6. Select **Basic cluster** for this lab. If a feature requires Enhanced, review the change and its charges before selecting Enhanced instead.
7. Choose **Flannel overlay** for pod networking. Set pod CIDR `10.244.0.0/16` and service CIDR `10.96.0.0/16` where prompted.

### 3. Configure networking

1. VCN: `p01-vcn`.
2. Kubernetes API endpoint: **Public endpoint**, subnet `p01-subnet-public-lb`.
3. Enable **Assign a public IP address to the API endpoint**.
4. Attach `p01-oke-api-nsg` to the API endpoint.
5. For Kubernetes Service load balancers, select public subnet `p01-subnet-public-lb`. Use one regional subnet.
6. Keep the existing network resources; do not choose an option that creates a new VCN.

### 4. Configure the managed node pool

1. Add a **managed node pool**, named `p01-oke-pool-01`.
2. Set its Kubernetes version to the version selected for the cluster.
3. Choose availability domain `sgUC:EU-FRANKFURT-1-AD-3` (use the tenancy's actual AD-3 name).
4. Select subnet `p01-subnet-private-vm` and attach `p01-oke-worker-nsg`.
5. Select shape **VM.Standard.E5.Flex**, **2 OCPUs**, **8 GB memory** per node.
6. Choose **Change image / Browse all images → OKE Worker Node Images** (sometimes labeled **OKE images**).
7. Filter Oracle Linux 8 and select build `2026.10.16-0` compatible with your Kubernetes version and E5 shape. Verify its full name/OCID. Do not choose a generic platform image, ARM image or GPU image.
8. Set **node count to 3**. Keep only the specified AD placement.
9. Disable legacy IMDS endpoints if the workflow exposes this setting. If it does not, create the cluster first, then use Cloud Shell before any pool scale-out:

   ```bash
   oci ce node-pool update --node-pool-id YOUR_NODE_POOL_OCID \
     --node-metadata '{"areLegacyImdsEndpointsDisabled":"true"}'
   ```

   This only affects newly launched workers. For an existing pool that still allows IMDSv1, create a replacement pool with the setting, verify it, and drain/delete the old pool. If the tenancy rejects worker creation because IMDSv1 is enabled, use Option B, which specifies this setting at pool creation.
10. SSH access is not required; no SSH key or TCP 22 rule is needed for this lab.

### 5. Create and verify

1. Review all settings, especially public API access, Flannel, image, worker subnet and per-node resources.
2. Choose **Create cluster**. Wait for the cluster and node pool to become **Active**, and all three workers to finish provisioning.
3. On the cluster page select **Access cluster**, choose **Local access**, and follow the displayed command to generate kubeconfig for the **public endpoint**. Use a separate kubeconfig file to preserve your existing contexts.
4. Run the checks in the following section.

### 6. Connect and check readiness (either deployment option)

For a local terminal, replace the cluster OCID below with the actual value. OCI Cloud Shell can also be used, but its egress must be allowed by the API NSG, or it must have a suitable private network path. Do not assume that your laptop's `/32` also permits Cloud Shell.

```bash
oci ce cluster create-kubeconfig --cluster-id YOUR_CLUSTER_OCID \
  --file ./kubeconfig-p01-oke --region eu-frankfurt-1 \
  --token-version 2.0.0 --kube-endpoint PUBLIC_ENDPOINT

export KUBECONFIG="$PWD/kubeconfig-p01-oke"
kubectl cluster-info
kubectl get nodes -o wide
kubectl wait --for=condition=Ready nodes --all --timeout=15m
kubectl get pods -n kube-system
```

**Success criteria:** cluster/node pool Active; exactly three nodes, all `Ready`; core system pods running or successfully completed; node private IPs belong to the worker subnet. Check actual Kubernetes patch versions in `kubectl get nodes` and cluster details. Inspect a worker's compute details to confirm E5, 2 OCPUs and 8 GB RAM.

## Option B - Deployment steps for Terraform

### 1. Review the files

```text
oke-lab/
  README.md
  terraform/
    versions.tf
    variables.tf
    terraform.tfvars.example
    main.tf
    network.tf
    outputs.tf
    .gitignore
    .terraform.lock.hcl
```

There is one README for this lab. `terraform.tfvars` is the participant parameter file; do not edit resource blocks to change normal lab settings. The CNI parameter intentionally accepts only Flannel because VCN-native networking needs additional resources.

Terraform creates the cluster, managed node pool, two NSGs and their rules. VCNs/subnets are looked up by exact display name within the network compartment and region. Missing, ambiguous or null lookup results receive explicit checks. The existing VCN, subnets, routing, gateways and security lists remain managed by the network lab.

### 2. Configure parameters and authentication

```bash
cd oke-lab/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

1. Replace `compartment_id` and `network_compartment_id` with real OCIDs. This lab expects the VCN and all three subnet roles in the network compartment specified.
2. Set `api_allowed_cidrs = ["YOUR_ACTUAL_PUBLIC_IPV4/32"]` to your actual egress CIDR. The initial empty value intentionally blocks planning until filled.
3. Keep or change the requested defaults. `config_file_profile` selects your local OCI API key profile; credentials stay in the OCI configuration/key files, outside this package.
4. Confirm the AD name, version and image using the preflight commands. For a named profile, add `--profile PROFILE_NAME` to CLI commands too.
5. Leave `node_image_id = ""` for strict image discovery. Exactly one source must match the build regex and selected Kubernetes version. If multiple sources match, set `node_image_id` to the exact compatible regional OCID. An explicit OCID overrides the name/date regex but must still appear in OKE's sources and match the selected version; you are responsible for checking OL8, architecture and shape compatibility.
6. If changing region/shape, also update AD, network names, image selector/OCID and resource sizing. `node_shape_config` is intended for flexible shapes.

### 3. Initialize and inspect the plan

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out=oke.tfplan
```

The included `.terraform.lock.hcl` records OCI provider 8.29.0. Commit it with the lab; initialization reuses the locked provider. The provider range is intentionally bounded; test upgrades before updating the lock file for a training cohort. Keep the plan file private.

Confirm that the plan creates one cluster, one pool of three nodes, and NSGs/rules. It must not replace the existing network or deploy a standalone load balancer. Image/version checks may stop planning if OKE does not offer the requested combination. A plan does not reserve E5 capacity or prove connectivity.

### 4. Deploy

```bash
terraform apply oke.tfplan
terraform output
```

Allow provisioning to finish. If you change the parameters after saving a plan, generate a new plan before applying. Do not run these commands against another lab's state directory.

### 5. Access and verify

```bash
terraform output -raw kubeconfig_command
```

Copy and run the printed command. It writes `./kubeconfig-p01-oke` and uses the configured region/profile. Then run the readiness checks from Option A, step 6. If you set `api_public_ip_enabled = false`, the command selects the private endpoint and your terminal must have a routed private connection to the VCN.

Changing a node image or metadata affects new workers; do not assume an existing pool's nodes are automatically rebuilt. Use a replacement pool and controlled drain for later changes.

## Troubleshooting

| Symptom | What to check / change |
| --- | --- |
| Version unavailable / HTTP 400 | Query cluster and node-pool options in Frankfurt. Minor and exact patch lists differ. Set `kubernetes_version` to an offered value; do not assume a catalog image means its control plane version is offered. |
| No compatible image / multiple images | Inspect OKE `sources`. Verify build date, version and x86 architecture. Pin a verified regional `node_image_id`, or change the date regex/version after instructor agreement. No fallback is automatic. |
| VCN/subnet not found, null results or multiple matches | Verify provider region, network compartment OCID, exact names and IAM; remove ambiguous names. Lookups do not search child compartments recursively. |
| Invalid AD | `sgUC` belongs to one tenancy. Query your availability domains and replace the full AD name. |
| Workers fail to launch / capacity error | Check E5 AD-3 capacity, quotas, boot volume limits and image compatibility. An instructor-approved AD change must also match an AD-specific worker subnet. |
| IMDSv1 restriction error | Keep `disable_legacy_imds = true`. Terraform passes the OKE node metadata setting at creation; a Console pool may need replacement with this setting. |
| Nodes stay NotReady | Check work request errors, worker NAT/service gateway routes, DNS, worker self traffic (including UDP 8472), API TCP 6443/12250 and API-to-worker TCP rules. Check available subnet IPs. |
| kubectl timeout | Confirm public API IP, IGW route, TCP 6443 ingress and actual VPN/NAT source address. A private endpoint needs a private path. Allow Cloud Shell's own egress if using it. |
| kubectl Unauthorized / Forbidden | Check OCI CLI profile, API credentials, cluster OCID, generated kubeconfig and OKE IAM/Kubernetes RBAC permissions. A public IP does not provide authorization. |
| API reachable from unexpected sources | Audit all attached security lists/NSGs; their allows are additive. Restrict broad 6443 ingress carefully in the network-owning stack. |
| Service EXTERNAL-IP stays Pending later | This lab only selects an LB subnet. Check Service events, LB quotas/IAM, public subnet capacity and required listener/backend security rules before adding a Service. |
| Changed parameters but existing workers unchanged | New image/metadata generally applies to new workers. Create a replacement pool, migrate workloads and remove the old pool. |

## Optional cleanup

Delete Kubernetes workloads and Services first, particularly `LoadBalancer` Services and PVCs. Wait for their cloud resources to be removed, and check retained volumes separately.

**Console deployment:** delete the managed node pool and wait for worker termination, delete the cluster, then delete the two lab NSGs once detached. Inspect remaining boot/block volumes and load balancers. Keep shared network resources for other labs.

**Terraform deployment**, from this lab's `terraform` directory:

```bash
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
```

Review the destroy plan before applying. Terraform removes resources in this lab's state; it does not own the reused network. Remove any service-created load balancers first because their VNICs or attachments can block cleanup. After successful cleanup, remove the lab kubeconfig and unset `KUBECONFIG` if you set it for this session. Preserve state until you confirm cleanup is complete.

## Oracle documentation references

- [OKE Custom Create workflow](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengcreatingclusterusingoke_topic-Using_the_Console_to_create_a_Custom_Cluster_with_Explicitly_Defined_Settings.htm)
- [Supported Kubernetes versions and preview notes](https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengaboutk8sversions.htm)
- [Version selection: minor versus exact patch](https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengupgradeoverview.htm)
- [Supported worker images and shapes](https://docs.oracle.com/en-us/iaas/Content/ContEng/Reference/contengimagesshapes.htm)
- [Oracle Linux 8 OKE image catalog](https://docs.oracle.com/en-us/iaas/images/oke-worker-node-oracle-linux-8x/)
- [OKE network requirements](https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengnetworkconfig.htm)
- [Example OKE network configurations](https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengnetworkconfigexample.htm)
- [OKE IAM policies](https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengpolicyconfig.htm)
- [Configuring worker IMDS](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengconfiguringimds.htm)
- [Terraform: OKE cluster](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/containerengine_cluster.html)
- [Terraform: managed node pool](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/containerengine_node_pool.html)
- [Terraform: node pool options](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/d/containerengine_node_pool_option.html)

Documentation reviewed: 17 November 2026. Regional OKE API options are the deployment-time check for versions and images. Verification: `terraform fmt -check` passed and `terraform init -backend=false` installed OCI provider 8.29.0 with verified signature. Full `terraform validate` could not run in the authoring environment because the sandbox blocks the provider plugin Unix socket. Run `terraform validate` and `terraform plan` in your own environment before deployment. This package has not been deployed into a tenancy by its author.
