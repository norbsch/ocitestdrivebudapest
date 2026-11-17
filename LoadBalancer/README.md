# Load Balancer Hands-on Lab

**Project:** OCITestDriveBudapest

## Goal / Estimated time

Create a public OCI Flexible Load Balancer that distributes HTTP traffic across two existing VM web servers using Round Robin. Configure HTTP health checks, update security lists manually, and test traffic distribution and backend failure recovery.

**Estimated time:** 30–45 minutes, assuming the compartment, network, and VMs already exist.

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

Complete the Compartment, Network, and VM labs. Only `p01-vm-01` and `p01-vm-02` are load balancer backends; `p01-vm-03` remains reserved for the LLM gateway.

Have the following resources available in **Germany Central (Frankfurt), `eu-frankfurt-1`**, or change the region consistently:

| Existing resource | Expected configuration |
| --- | --- |
| Lab compartment | Your training compartment; record its OCID |
| VCN | `p01-vcn`, `10.0.0.0/16` |
| Public LB subnet | `p01-subnet-public-lb`, `10.0.0.0/24`; regional for this single-subnet public LB configuration |
| Private VM subnet | `p01-subnet-private-vm`, `10.0.1.0/24` |
| Backend VMs | `p01-vm-01` and `p01-vm-02`, both running, with reachable private IPv4 addresses |
| Public subnet routing | `0.0.0.0/0` → enabled Internet Gateway |
| Administration access | SSH through your existing bastion, OCI Bastion session, or another approved private connection |

Use your existing private VM subnet if its display name differs. The Terraform code discovers backend addresses from each VM's primary VNIC and does not look up the VM subnet by name. It expects unique VM display names within the selected backend compartment. Keep backends in this VCN for this lab.

### 2. Confirm permissions and capacity

You need IAM access to create/manage load balancers, use the existing network, inspect VMs/VNIC attachments, read VNIC details, and edit the relevant subnet security lists. Ask your training administrator to confirm these permissions and available Load Balancer quota. The Terraform code does not create IAM policies.

The flexible LB can scale to **100 Mbps** in this exercise; check your tenancy's applicable charges and quotas before deployment. Use HTTP only for this training exercise; configure TLS separately before serving sensitive application traffic.

### 3. Choose a deployment option

Choose **Option A - OCI Console** or **Option B - Terraform**. Both options create the target configuration below. Use one option for each lab deployment; do not create the same resources with both options.

Use your assigned attendee prefix in place of `p01`, consistently across all labs. Follow the workshop order: **Compartment → Network → VM → Load Balancer → PostgreSQL → OKE**.

For Option B, follow the two authentication methods in [Prepare the environment and authentication](#2-prepare-the-environment-and-authentication). Keep attendee settings in `terraform.tfvars` and use a separate Terraform directory and state for each lab and attendee.

### 4. Prepare the backend web servers

If both servers already serve HTTP on port 80 with distinguishable pages, verify them and continue. Otherwise, connect to each VM using the administration access above and run the commands for its operating system. Package installation from a private subnet needs working outbound access, such as a NAT Gateway or an approved package mirror.

**Oracle Linux** — run on each VM:

```bash
sudo dnf install -y httpd
printf '<h1>Backend: %s</h1>\n' "$(hostname)" | sudo tee /var/www/html/index.html
sudo systemctl enable --now httpd
```

If `firewalld` is active, permit traffic from the LB subnet:

```bash
sudo firewall-cmd --state
# Run the following only if the previous command reports running.
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="10.0.0.0/24" port port="80" protocol="tcp" accept'
sudo firewall-cmd --reload
```

**Ubuntu 24.04** — run on each VM:

```bash
sudo apt-get update
sudo apt-get install -y nginx
printf '<h1>Backend: %s</h1>\n' "$(hostname)" | sudo tee /var/www/html/index.html
sudo systemctl enable --now nginx
```

If UFW is active, add the rule below. Preserve the existing SSH access rules:

```bash
sudo ufw status
# Run the following only if UFW is active.
sudo ufw allow from 10.0.0.0/24 to any port 80 proto tcp
```

Other host firewall rules, including image-provided iptables/nftables rules, must also permit the traffic. Inspect the active rules if remote HTTP still fails; keep the firewall enabled.

On each VM, verify the page and listening socket:

```bash
curl -i http://127.0.0.1/
sudo ss -lntp | grep ':80 '
```

Expect HTTP `200` and a socket bound to the VM's private address or all interfaces, rather than only `127.0.0.1`. Record each VM's primary private IP from **Compute → Instances → instance details → Attached VNICs → primary VNIC**. If both pages show the same hostname, edit their headings to `p01-vm-01` and `p01-vm-02` respectively.

### 5. Prepare network security

1. Open **Networking → Virtual cloud networks → p01-vcn → Subnets**.
2. Open `p01-subnet-public-lb`, then a security list attached to that subnet.
3. Add the first two rules below if equivalent rules do not already exist.
4. Open the private VM subnet and a security list attached to it. Add the backend ingress rule below.
5. Use **TCP**, **source port: All**, and **stateful rules**: leave **Stateless** unchecked.

| Security list attached to | Direction | Source / destination CIDR | Destination port | Purpose |
| --- | --- | --- | --- | --- |
| Public LB subnet | Ingress | Source `0.0.0.0/0` | `80` | Internet clients reach the HTTP listener |
| Public LB subnet | Egress | Destination `10.0.1.0/24` | `80` | LB reaches backend HTTP and health checks |
| Private VM subnet | Ingress | Source `10.0.0.0/24` | `80` | Backends accept LB requests and health checks |

An existing egress rule allowing all traffic already covers the LB egress requirement. Stateful rules allow the response traffic automatically. Preserve existing administration and application rules. Check every security list attached to the subnets and any existing NSGs when diagnosing traffic; avoid duplicate rules. If backends are in different subnets, permit each actual backend CIDR.

These CIDRs match the prerequisite network lab. Adjust them if you changed that lab. If you change listener, backend, or health-check ports in Terraform, update the corresponding security-list and host-firewall rules too. A different health-check port needs its own LB egress/backend ingress permission.

**Terraform does not manage security lists or NSGs in this lab.** Make changes in the network lab's source configuration as well if those lists are already managed by another Terraform state, so its next apply does not remove your manual changes.

## Target configuration

### Resource settings

| Setting | Default | Terraform parameter in `terraform.tfvars` |
| --- | --- | --- |
| Region | `eu-frankfurt-1` | `region` |
| LB display name | `p01-lb-01` | `load_balancer.name` |
| Visibility | Public | `load_balancer.is_private = false` |
| Public IP | Ephemeral | `load_balancer.reserved_public_ip_id = null` |
| VCN | `p01-vcn` | `network.vcn_name` |
| LB subnet | `p01-subnet-public-lb` | `network.subnet_name` |
| Shape | Flexible | Fixed lab resource shape |
| Minimum / maximum bandwidth | `10` / `100` Mbps | `load_balancer.minimum_bandwidth_in_mbps` / `maximum_bandwidth_in_mbps` |
| Backend set | `p01-backendset-http` | `backend_set.name` |
| Policy | Round Robin | `backend_set.policy = "ROUND_ROBIN"` |
| Backends | `p01-vm-01:80`, `p01-vm-02:80` | `backends` map, with VM names as keys |
| Backend weights | `1` each | `backends["VM_NAME"].weight` |
| Health check | HTTP, port `80`, path `/`, status `200` | `health_check` object |
| Health timing | Interval `10000` ms, timeout `3000` ms, retries `3` | `health_check` object |
| Listener | `p01-listener-http-80`, HTTP `80` | `listener` object |
| Listener idle timeout | `60` seconds | `listener.idle_timeout_in_seconds` |
| Security lists | Manually configured | Before you begin, step 5 |

The default public IP is allocated by OCI. To use an existing reserved public IP, supply its OCID in `reserved_public_ip_id`. To make a private LB, set `is_private = true`, leave that ID null, select an appropriate subnet, and test from a client with VCN access. These changes may replace the LB; review the plan. This lab's listener supports plain HTTP; HTTPS requires additional certificate and SSL configuration.

## Option A - Deployment steps for OCI Console

### 1. Open the Load Balancer creation wizard

1. Sign in to the OCI Console and select the correct region and lab compartment.
2. Open **Networking → Load balancers**. Use the Console search if the navigation label differs.
3. Select **Create load balancer** and select the **Load Balancer** service if prompted. This lab uses Flexible Load Balancer, not Network Load Balancer.

### 2. Configure the front end

1. Name: `p01-lb-01`.
2. Visibility: **Public**; public IP assignment: **Ephemeral IP address**.
3. Shape: **Flexible**; minimum `10` Mbps; maximum `100` Mbps.
4. VCN: `p01-vcn`; subnet: `p01-subnet-public-lb`.
5. Use IPv4 for this exercise. Leave optional NSGs unselected.

### 3. Configure backends

1. Set the backend-set name to `p01-backendset-http` where the wizard allows it. If it assigns a generated name, record that name for the listener.
2. Select **Round Robin**.
3. Add `p01-vm-01` and `p01-vm-02` from their compartment, each on port `80` with weight `1`. Confirm their addresses match the recorded primary private IPs.
4. Health check: **HTTP**, port `80`, URL path `/`, expected status `200`.
5. Set interval `10000` ms, timeout `3000` ms, and retries `3`, if shown in advanced settings. Keep backend SSL and session persistence disabled.
6. Select **Manually configure security list rules** wherever the wizard prompts for security-rule management. The rules were configured in Before you begin, step 5.

### 4. Configure the listener and create

1. Listener name: `p01-listener-http-80`; protocol: **HTTP**; port: `80`.
2. Route to the backend set created above. Use a `60` second idle timeout if this setting is shown.
3. For this basic lab, leave optional access/error logging disabled. You can enable it later for troubleshooting.
4. Review the configuration and select **Create load balancer**.
5. Wait for **Active**, then record the public IP. Open **Backend sets → your backend set → Backends** and wait for both backends to report healthy/OK. If needed, use the backend set/listener edit pages to confirm settings the wizard did not expose.

### 5. Verify deployment

From your workstation or Cloud Shell, replace the placeholder and run:

```bash
LB_URL="http://REPLACE_WITH_LB_PUBLIC_IP:80/"
for i in $(seq 1 20); do
  curl --fail --silent --show-error --max-time 10 -H 'Connection: close' "$LB_URL"
  printf '\n'
done
```

Expect successful responses showing both VM identities. Do not use strict request-by-request alternation as a pass/fail test; concurrent traffic and LB connection handling can affect the observed order.

To test failure recovery, stop the web server on **one backend only**:

```bash
sudo systemctl stop nginx
```

Use `httpd` instead of `nginx` if you deliberately chose Oracle Linux.

Wait for its health status to become unhealthy, then rerun the requests. Responses should come from the remaining healthy VM. Requests during detection can fail. Restart the service (`sudo systemctl start httpd`, or `nginx` on Ubuntu), wait for healthy status, and verify both names return again.

**Success criteria:** LB Active; both backends healthy after recovery; HTTP responses received through the public address from both VMs.

## Option B - Deployment steps for Terraform

Complete **Before you begin** first. This lab has one README for both deployment options. Run all Terraform commands from `LoadBalancer/terraform/` in your repository checkout.

### 1. Review the Terraform files

All paths in this table are relative to `LoadBalancer/terraform/`.

| File | Purpose |
| --- | --- |
| `versions.tf` | Defines the supported Terraform and OCI provider versions. |
| `provider.tf` | Configures the OCI region and selected authentication method. |
| `variables.tf` | Declares input parameters, types, and validation rules. |
| `terraform.tfvars.example` | Provides the example lab settings; copy it to `terraform.tfvars`. |
| `terraform.tfvars` | Contains your local attendee settings; created in step 3 and kept out of Git. |
| `main.tf` | Looks up the existing network and backends, then creates the load balancer resources. |
| `outputs.tf` | Reports the load balancer OCID, IPs, listener URL, and resolved backend addresses. |
| `.terraform.lock.hcl` | Records the selected provider version and checksums; created or reused by `terraform init` and committed after review. |

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
cd LoadBalancer/terraform
cp terraform.tfvars.example terraform.tfvars
```

If `terraform.tfvars` already exists, edit that file instead of overwriting it. Set the authentication values from step 2, then review the following lab inputs:

| Parameter | What to enter or check |
| --- | --- |
| `region`, `compartment_id` | Existing network region and target load balancer compartment OCID. |
| `network_compartment_id` | Network compartment OCID, or `null` to reuse `compartment_id`. |
| `backend_compartment_id` | VM compartment OCID, or `null` to reuse `compartment_id`. |
| `network` | Exact names of the VCN and public load balancer subnet. |
| `load_balancer` | Name, public visibility, ephemeral IP (`reserved_public_ip_id = null`), and 10–100 Mbps bandwidth. |
| `backend_set` | Name and `ROUND_ROBIN` policy. |
| `backends` | VM 1 and VM 2 display names as keys, each with port 80 and weight 1. |
| `health_check` | HTTP, port 80, `/`, expected status 200, and timing settings. |
| `listener` | HTTP port 80, listener name, and 60-second idle timeout. |

The VCN and LB subnet must be in the same configured network compartment. Backends must already be running. Terraform finds each backend's primary VNIC and uses its private IP, even when additional VNICs are attached. Names must identify exactly one resource in the selected scope.

Keep VM 3 out of the `backends` map. If you change listener, backend, or health-check ports, update the manual security-list and host-firewall rules in **Before you begin, step 5** as well.

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

For a new deployment with two backends, expect **5 to add, 0 to change, 0 to destroy**: one load balancer, one backend set, two backend registrations, and one listener. Verify the selected subnet, resolved backend IPs, listener, health check, and bandwidth settings. The existing VCN, subnets, VMs, and security lists must not change.

Review the complete plan before applying. Stop if it includes unexpected changes or deletions. If you edit parameters after saving the plan, create and review a new plan.

### 6. Apply the reviewed plan

```bash
terraform apply lab.tfplan
terraform output
```

Applying a saved plan executes its reviewed changes without a second approval prompt. Wait for completion and keep the Terraform state for later updates and cleanup. If an apply only partially succeeds, retain the state, resolve the error, and create a fresh plan.

### 7. Verify deployment

```bash
terraform output backend_endpoints
terraform output -raw listener_url
```

Confirm the load balancer is **Active** and both backends are healthy in the OCI Console. Terraform configures the LB; it does not install or verify the web servers.

From this Terraform directory, test the listener:

```bash
LB_URL="$(terraform output -raw listener_url)"
for i in $(seq 1 20); do
  curl --fail --silent --show-error --max-time 10 -H 'Connection: close' "$LB_URL"
  printf '\n'
done
```

Complete the failure/recovery exercise in [Option A, step 5](#5-verify-deployment).

**Success criteria:** The LB is Active, both backends are healthy after recovery, and requests to its public URL return pages from both VMs.

### 8. Update the configuration

Edit `terraform.tfvars` for routine changes, then repeat steps 4–7 with the same working directory and state. Generate a new plan each time. Avoid editing Terraform-managed resources directly in the Console, and never manage the same resource from two Terraform states.

Replan if a backend VM address changes, and keep security-list and host-firewall rules aligned with any port changes.

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
| No VCN, subnet, or VM match | Confirm region, exact display name, resource state, compartment OCIDs, and IAM access. Lookups do not search child compartments automatically. |
| More than one matching resource | Give lab resources unique display names within the lookup scope, then update the parameter file. |
| `NotAuthorizedOrNotFound` / 404 | Verify the selected OCI identity, region, OCIDs, and permissions across LB, network, and backend compartments. |
| Public LB cannot be created in subnet | Confirm the LB subnet is regional, allows public IPs, and has enough available addresses. This lab uses one regional public subnet; an AD-specific public LB requires two subnets in different ADs. |
| Quota / bandwidth error | Confirm available LB quota and supported bandwidth in the selected region. Use whole Mbps, with minimum no greater than maximum. |
| LB is Active but all backends unhealthy | Confirm server processes, private IPs, port 80 bindings, LB egress, VM ingress, and host firewalls. From a client allowed by your security rules, test each backend's private address directly. |
| Health checks fail with status mismatch | `curl -i http://127.0.0.1/` on the backend should return 200 for `/`. Fix redirects, authentication, virtual-host requirements, or choose a suitable health path/status. |
| Public request times out | Check public LB IP, HTTP URL/port, Internet Gateway route, LB ingress, and any intervening client/proxy firewall. |
| HTTP 502/504 or intermittent errors | Check backend health, response times, listener/backend ports, and application logs. Enable LB error logs if needed. |
| Only one backend page appears | Confirm both backends are healthy with equal weights, pages differ, and no persistence is enabled. Use the curl loop to avoid browser caching effects. |
| Rules disappear after the network lab is applied | Add the intended rules to that lab's Terraform configuration; its state may own the security list. |
| Another operation is already in progress | Wait for the LB work request to finish and retry. If concurrent LB operations repeatedly conflict, create and review a fresh `lab.tfplan`, then use `terraform apply -parallelism=1 lab.tfplan`. |

Inspect the LB's **Work requests**, backend health details, and web-server logs when troubleshooting. Changes to security rules and servers can take time to appear in health status.

## Optional cleanup

Remove this load balancer when its traffic-distribution exercise is complete and no application still needs it. Use the same deployment option that created each resource.

### Option A - OCI Console

1. Open the Load Balancer page and select `p01-lb-01`.
2. Delete the load balancer and wait for deletion to finish. Its listener, backend set, backend registrations, and ephemeral public IP are removed with it.
3. Keep the existing backend VMs and network if other labs still use them.

### Option B - Terraform

From `LoadBalancer/terraform/`, use the original state and parameter file. Create a cleanup plan:

```bash
terraform plan -destroy -out=cleanup.tfplan
terraform show cleanup.tfplan
```

Confirm the plan removes only the five default LB resources. The existing VCN, subnet, and VMs are read through data sources and are not deleted. An externally created reserved public IP is not owned by this configuration.

After reviewing the plan, apply it:

```bash
terraform apply cleanup.tfplan
```

For either deployment option, remove only security-list and host-firewall rules added exclusively for this lab when no longer needed. Reconcile any Terraform-managed rules through the owning Network lab. If you installed a web server only for this exercise, stop/disable it or restore its previous configuration.

Keep Terraform state until cleanup is confirmed. Delete shared network resources and the compartment only after all dependent labs are finished.

## Oracle documentation references

- [Load Balancer overview](https://docs.oracle.com/en-us/iaas/Content/Balance/Concepts/balanceoverview.htm)
- [Create a Load Balancer](https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managingloadbalancer_topic-Creating_Load_Balancers.htm)
- [Getting started with Load Balancing and security rules](https://docs.oracle.com/en-us/iaas/Content/GSG/Tasks/loadbalancing.htm)
- [Load balancing policies](https://docs.oracle.com/en-us/iaas/Content/Balance/Reference/lbpolicies.htm)
- [Health check policies](https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/load_balancer_health_management.htm)
- [OCI provider: Load Balancer](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/load_balancer_load_balancer.html)
- [OCI provider: backend set](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/load_balancer_backend_set.html)
- [OCI provider: backend](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/load_balancer_backend.html)
- [OCI provider: listener](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/load_balancer_listener.html)
- [OCI provider: configuration and authentication](https://docs.oracle.com/en-us/iaas/Content/terraform/configuring.htm)
- [OCI Terraform provider configuration and authentication](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/configuring.htm)
- [Using OCI Cloud Shell](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/devcloudshellgettingstarted.htm)
- [OCI SDK and CLI configuration file](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
