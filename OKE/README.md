# OKE Hands-on Lab

**Project:** OCITestDriveBudapest

## Goal / Estimated time

Create an OKE cluster in the existing `p01-vcn` with a public Kubernetes API endpoint and three private managed worker nodes. Use either the OCI Console or Terraform, then connect with `kubectl` and verify that all workers are ready.

**Estimated time:** 45–60 minutes, including provisioning. This lab creates billable compute and boot volumes. It reuses the network from the network lab.

## Contents

- [Goal / Estimated time](#goal--estimated-time)
- [Before you begin](#before-you-begin)
- [Target configuration](#target-configuration)
- [Option A - Deployment steps for OCI Console](#option-a---deployment-steps-for-oci-console)
- [Option B - Deployment steps for Terraform](#option-b---deployment-steps-for-terraform)
- [Troubleshooting](#troubleshooting)
- [Optional cleanup](#optional-cleanup)
- [Oracle documentation references](#oracle-documentation-references)

## Before you begin

### 1. Confirm the prerequisites

1. Complete the Compartment and Network labs. Record the resource compartment OCID and network compartment OCID; they may be identical.
2. Sign in to the OCI Console and select **Germany Central (Frankfurt)** (`eu-frankfurt-1`), matching your existing network.
3. Verify that `p01-subnet-public-lb` is public and regional, and `p01-subnet-private-vm` is private and regional (or AD-3-specific). Leave sufficient unused IP addresses for the API endpoint, workers, and future load balancers.
4. Check the existing routes: the public subnet needs an Internet Gateway default route; private workers need a NAT Gateway default route and a Service Gateway route for the regional **All <region> Services in Oracle Services Network** service CIDR. Enable VCN DNS resolution using Internet and VCN Resolver DHCP options.
5. Identify the public IPv4 egress CIDR of the terminal that will run `kubectl`, such as your laptop/VPN or Cloud Shell. Use the address seen by OCI after NAT/VPN. A laptop `/32` does not also permit Cloud Shell.
6. Have OCI CLI and `kubectl` compatible with the selected server version. Use your configured local OCI CLI profile or Cloud Shell's existing CLI session. Keep private keys, credentials, kubeconfig, and Terraform state out of Git.

### 2. Confirm permissions and capacity

Confirm permissions to manage OKE clusters/node pools, compute instances, VNICs, volumes, and NSGs, and to use the existing VCN/subnets and gateways. Ask the instructor to verify IAM using Oracle's OKE policy reference. Cluster access also requires Kubernetes authorization.

Check E5 capacity and limits for **6 OCPUs, 24 GB RAM, and three worker boot volumes** in AD3. The AD prefix `sgUC` is tenancy-specific; copy the full AD name from your tenancy. Review applicable compute and storage charges.

### 3. Choose a deployment option

Choose **Option A - OCI Console** or **Option B - Terraform**. Both options create the target configuration below. Use one option for each lab deployment; do not create the same resources with both options.

Use your assigned attendee prefix in place of `p01`, consistently across all labs. Follow the workshop order: **Compartment → Network → VM → Load Balancer → PostgreSQL → OKE**.

For Option B, follow the two authentication methods in [Prepare the environment and authentication](#2-prepare-the-environment-and-authentication). Keep attendee settings in `terraform.tfvars` and use a separate Terraform directory and state for each lab and attendee.

### 4. Confirm available versions and images

The requested default is **`v1.37`**, with an Oracle Linux 8 OKE worker image using build **`2026.10.16-0`**. Confirm that OKE offers this version and image combination in your tenancy and region before provisioning. A minor version selects the patch offered by OKE; record the actual patch after deployment.

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

Look for a **standard x86 Oracle Linux 8 OKE worker image** containing build **`2026.10.16-0`** and the selected Kubernetes version. Exclude `aarch64` and GPU images for this E5 CPU shape. Record the exact image name and regional OCID from OKE's response. The date is part of the underlying image build name; it is not necessarily the OKE image publication date.

If the requested combination is unavailable, stop and agree on an available version/image combination with the instructor, then update the Console choices or parameter file. Preview versions are for testing and have limited support.

## Target configuration

### Resource settings

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

### 6. Verify deployment

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

Complete **Before you begin** first. This lab has one README for both deployment options. Run all Terraform commands from `OKE/terraform/` in your repository checkout.

### 1. Review the Terraform files

All paths in this table are relative to `OKE/terraform/`.

| File | Purpose |
| --- | --- |
| `versions.tf` | Defines the supported Terraform and OCI provider versions. Also configures the OCI region and selected authentication method. |
| `variables.tf` | Declares input parameters, types, and validation rules. |
| `terraform.tfvars.example` | Provides the example lab settings; copy it to `terraform.tfvars`. |
| `terraform.tfvars` | Contains your local attendee settings; created in step 3 and kept out of Git. |
| `main.tf` | Looks up the existing network and available OKE options, then creates the cluster and node pool. |
| `network.tf` | Creates the API and worker NSGs and their security rules. |
| `outputs.tf` | Reports cluster/node pool OCIDs, API endpoints, NSG OCIDs, the image, and a kubeconfig command. |
| `.terraform.lock.hcl` | Records the selected provider version and checksums; created or reused by `terraform init` and committed after review. |

OKE keeps its provider block in `versions.tf`; it has no separate `provider.tf`.

Keep normal lab changes in `terraform.tfvars`; use `variables.tf` to check accepted inputs. Provider version constraints stay in `versions.tf`.

### 2. Prepare the environment and authentication

Use **Terraform 1.5 or later, below 2.0**, as required by `versions.tf`. The OCI provider constraint for this lab is `>= 7.0.0, < 9.0.0`. Terraform installs the provider during initialization. The command examples use Bash, available in OCI Cloud Shell and common Linux/macOS terminals. On Windows, use a compatible shell or adapt the shell syntax.

Choose one of the following authentication methods. In this lab, `auth_method` is the input that sets the OCI provider's `auth` argument. Add the selected values to `terraform.tfvars` in step 3.

#### Local machine (`auth = "APIKey"`)

Install Terraform CLI and configure an OCI API-signing-key profile in `~/.oci/config`. The profile must contain `tenancy`, `user`, `fingerprint`, and `key_file`. Register the matching public key with your OCI user, and keep the private key outside the repository.

```hcl
auth_method         = "APIKey"
config_file_profile = "DEFAULT"
```

Replace `DEFAULT` with your profile name if needed.

#### OCI Cloud Shell (`auth = "InstancePrincipal"`)

Open Cloud Shell from your signed-in OCI Console session. Terraform CLI is already installed; check its version with `terraform version`. Use Cloud Shell's existing authentication environment. You do not need to create an API-signing-key profile in `~/.oci/config` for this method.

```hcl
auth_method         = "InstancePrincipal"
config_file_profile = "DEFAULT"
```

Keep `config_file_profile = "DEFAULT"` in the parameter file with the current repository code: `variables.tf` still requires this input, although the provider passes it as `null` and ignores it when `auth_method = "InstancePrincipal"`. This value does not require a local `DEFAULT` API-key profile in Cloud Shell. Do not omit it unless the variable declaration has also been made optional.

Keep Cloud Shell's preconfigured authentication environment intact. The selected method must have the IAM permissions listed in **Before you begin**. Set `region` to the deployment region containing your lab network; normally `eu-frankfurt-1`.

### 3. Configure the lab parameters

From the repository root, open this lab's Terraform directory and create your local parameter file:

```bash
cd OKE/terraform
cp terraform.tfvars.example terraform.tfvars
```

If `terraform.tfvars` already exists, edit that file instead of overwriting it. Set the authentication values from step 2, then review the following lab inputs:

| Parameter | What to enter or check |
| --- | --- |
| `region`, `compartment_id`, `network_compartment_id` | Existing network region and both compartment OCIDs; use the same OCID if shared. |
| `vcn_name`, `api_subnet_name`, `lb_subnet_name`, `worker_subnet_name` | Exact existing VCN/subnet names from the target configuration. |
| `cluster_name`, `cluster_type`, `node_pool_name` | Attendee names and `BASIC_CLUSTER`. |
| `kubernetes_version`, `cni_type` | Offered version matching the requested `v1.37` and `FLANNEL_OVERLAY`. |
| `api_public_ip_enabled`, `api_allowed_cidrs` | Public endpoint enabled and actual client egress CIDR(s), such as `["YOUR_ACTUAL_PUBLIC_IPV4/32"]`. |
| `pods_cidr`, `services_cidr` | `10.244.0.0/16` and `10.96.0.0/16`; no overlap with each other or connected networks. |
| `availability_domain` | Your tenancy's full AD3 name. |
| `node_shape`, `node_ocpus`, `node_memory_gbs`, `node_count` | E5 flexible shape, 2 OCPUs, 8 GB per worker, and three workers. |
| `node_image_name_regex`, `node_image_id` | Verified OL8 OKE image build selector, or an exact compatible regional image OCID. |
| `disable_legacy_imds`, `freeform_tags` | Keep IMDSv1 disabled (`true`) and review tags. |

The initial empty `api_allowed_cidrs` deliberately blocks planning. Replace it with the egress CIDR(s) of the terminal that will run `kubectl`. The VCN and all subnet roles must be in `network_compartment_id`.

Complete the version/image preflight in **Before you begin, step 4**. Leave `node_image_id = ""` for strict discovery: exactly one OKE source must match the build regex and selected version. If several match, set the exact compatible regional OCID. An explicit OCID overrides the build regex but must still appear in OKE's sources and match the selected version; verify Oracle Linux 8, x86 architecture, and shape compatibility yourself.

If changing region or shape, also review the AD, network names, image selector, and sizing. The configuration accepts only Flannel; VCN-native networking requires a different network design.

Terraform loads `terraform.tfvars` automatically; no `-var-file` argument is needed. Keep credentials, private keys, local parameter files, state, plans, and `.terraform/` out of Git. Check the applicable `.gitignore` rules; the repository does not provide complete Terraform exclusions for every lab. Commit the Terraform source, sanitized `terraform.tfvars.example`, and reviewed provider lock file.

### 4. Initialize and validate

```bash
terraform init
terraform fmt -recursive
terraform validate
```

`init` installs the provider and creates or reuses `.terraform.lock.hcl`. `fmt` normalizes formatting; it does not change the intended infrastructure. `validate` checks configuration syntax and provider schema. Resolve errors before continuing. Retain the reviewed lock file for repeatable workshop runs; test provider upgrades before changing it.

### 5. Review the execution plan

```bash
terraform plan -out=lab.tfplan
terraform show lab.tfplan
```

Confirm the plan creates one cluster, one managed node pool containing three workers, two NSGs, and their rules. With one unique client CIDR, expect **13 to add, 0 to change, 0 to destroy**; each additional unique client CIDR adds one API ingress rule. The three workers are managed through the node pool, not as three separate Terraform instance resources.

Verify Flannel, the version/image, worker AD/subnet, per-node resources, public API setting, and allowed client CIDRs. Existing VCNs, subnets, routes, and security lists must not change. Selecting a Service load balancer subnet does not deploy a load balancer. A successful plan does not reserve E5 capacity or prove network connectivity.

Review the complete plan before applying. Stop if it includes unexpected changes or deletions. If you edit parameters after saving the plan, create and review a new plan.

### 6. Apply the reviewed plan

```bash
terraform apply lab.tfplan
terraform output
```

Applying a saved plan executes its reviewed changes without a second approval prompt. Wait for completion and keep the Terraform state for later updates and cleanup. If an apply only partially succeeds, retain the state, resolve the error, and create a fresh plan.

### 7. Verify deployment

```bash
terraform output -raw cluster_id
terraform output -raw node_pool_id
terraform output selected_worker_image
terraform output -raw kubeconfig_command
```

The current `kubeconfig_command` output always appends `--profile` using `config_file_profile`. On a local machine using APIKey, run it with your configured profile. In Cloud Shell, remove that trailing `--profile` option so OCI CLI uses Cloud Shell's existing session profile and authentication environment. Terraform authentication and OCI CLI authentication are separate settings.

Run the resulting command to create the separate lab kubeconfig, then complete [Option A, step 6](#6-verify-deployment). If `api_public_ip_enabled = false`, the output selects the private endpoint; your terminal must have a routed private connection to the VCN.

**Success criteria:** The cluster and pool are Active; exactly three workers are Ready; core system pods are running or successfully completed; worker placement, image, shape, and private IPs match the target configuration.

### 8. Update the configuration

Edit `terraform.tfvars` for routine changes, then repeat steps 4–7 with the same working directory and state. Generate a new plan each time. Avoid editing Terraform-managed resources directly in the Console, and never manage the same resource from two Terraform states.

Changing the node image or metadata affects newly launched workers. Use a replacement pool and a controlled workload drain when existing workers must be replaced.

## Troubleshooting

### Authentication and Terraform

| Symptom | What to check |
| --- | --- |
| APIKey authentication fails | Check the selected profile in `~/.oci/config`, tenancy/user OCIDs, fingerprint, key path, and registered public key. |
| Cloud Shell tries to open `~/.oci/config` | Select `InstancePrincipal` with this lab's authentication input. Confirm the current provider passes `config_file_profile = null` for this mode, and remove any custom profile override that forces local API-key lookup. Keep Cloud Shell's managed authentication environment. |
| Terraform prompts for `config_file_profile` in Cloud Shell | Keep `config_file_profile = "DEFAULT"` in `terraform.tfvars`; the current variable declaration requires a value even though the provider ignores it in this mode. |
| Cloud Shell session authentication fails | Start a fresh signed-in Cloud Shell session and retry with its preconfigured environment. Check IAM permissions if authentication succeeds but requests are denied. |
| Unexpected parameter prompt or undeclared-variable warning | Run commands from this lab's `terraform/` directory and use the exact input names declared in its `variables.tf`. |
| `terraform validate` fails | Check the reported file/line and provider version. Initialize the directory first; use the reviewed `.terraform.lock.hcl`. |
| Apply only partially succeeds | Keep state, resolve the reported error, then create and review a fresh plan before applying. |

### Lab-specific issues

| Symptom | What to check |
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

Delete Kubernetes workloads and their service-created resources before removing the cluster and workers. Use the same deployment option that created each resource.

### Option A - OCI Console

1. Delete Kubernetes workloads first, especially `LoadBalancer` Services and PVCs. Wait for their cloud resources to be removed, and review retained volumes separately.
2. Delete the managed node pool and wait for worker termination.
3. Delete the cluster.
4. Delete both lab NSGs after they are detached. Inspect remaining volumes and load balancers; retain shared network resources.

### Option B - Terraform

From `OKE/terraform/`, use the original state and parameter file. Create a cleanup plan:

```bash
terraform plan -destroy -out=cleanup.tfplan
terraform show cleanup.tfplan
```

Confirm the plan removes only the cluster, managed node pool, NSGs, and rules in this lab's state. Delete Kubernetes-created load balancers and volumes first; their attachments can block cleanup. The existing network belongs to the Network lab.

After reviewing the plan, apply it:

```bash
terraform apply cleanup.tfplan
```

After confirming cleanup, remove the lab kubeconfig and unset `KUBECONFIG` if you set it for this session. Check retained volumes and service-created resources separately.

Keep Terraform state until cleanup is confirmed. Delete shared network resources and the compartment only after all dependent labs are finished.

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
- [OCI Terraform provider configuration and authentication](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/configuring.htm)
- [Using OCI Cloud Shell](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/devcloudshellgettingstarted.htm)
- [OCI SDK and CLI configuration file](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
