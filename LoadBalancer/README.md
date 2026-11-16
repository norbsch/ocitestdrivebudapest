# OCI Public Load Balancer Hands-on Lab

**Project:** OCITestDriveBudapest

## Goal / Estimated Time for the Hands-on Lab

Create a public OCI Flexible Load Balancer that distributes HTTP traffic across two existing VM web servers using Round Robin. Configure HTTP health checks, update security lists manually, and test traffic distribution and backend failure recovery.

**Estimated time:** 30–45 minutes, assuming the compartment, network, and VMs already exist.

This is the Load Balancer lab for **OCITestDriveBudapest**. Choose **Option A** or **Option B** to create the same configuration. Both options require the preparation and manual security-list steps below.

## Contents

- [Before you begin](#before-you-begin)
- [Target configuration](#target-configuration)
- [Option A - Deployment steps for OCI Console](#option-a---deployment-steps-for-oci-console)
- [Option B - Deployment steps for Terraform](#option-b---deployment-steps-for-terraform)
- [Troubleshooting](#troubleshooting)
- [Optional cleanup](#optional-cleanup)
- [Oracle documentation references](#oracle-documentation-references)

## Before you begin

### 1. Complete the prerequisite labs

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

You need IAM access to create/manage load balancers, use the existing network, inspect VMs/VNIC attachments, read VNIC details, and edit the relevant subnet security lists. Ask your training administrator to confirm these permissions and available Load Balancer quota. The Terraform code does not create IAM policies.

The flexible LB can scale to **100 Mbps** in this exercise; check your tenancy's applicable charges and quotas before deployment. Use HTTP only for this training exercise; configure TLS separately before serving sensitive application traffic.

### 2. Prepare a web page on each VM

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

### 3. Manually configure security lists — required for both options

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

**Terraform deliberately does not manage security lists or NSGs.** There is no invented `security_list_management` setting in this LB configuration. Make changes in the network lab's source configuration as well if those lists are already managed by another Terraform state, so its next apply does not remove your manual changes.

## Target configuration

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
| Security lists | Manually configured | Preparation step 3 above |

The default public IP is allocated by OCI. To use an existing reserved public IP, supply its OCID in `reserved_public_ip_id`. To make a private LB, set `is_private = true`, leave that ID null, select an appropriate subnet, and test from a client with VCN access. These changes may replace the LB; review the plan. This lab's listener supports plain HTTP; HTTPS requires additional certificate and SSL configuration.

## Option A - Deployment steps for OCI Console

### 1. Open the Load Balancer creation wizard

1. Sign in to the OCI Console and select the correct region and lab compartment.
2. Open **Networking → Load balancers**. Use the Console search if the navigation label differs.
3. Click **Create load balancer** and select the **Load Balancer** service if prompted. This lab uses Flexible Load Balancer, not Network Load Balancer.

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
6. Select **Manually configure security list rules** wherever the wizard prompts for security-rule management. The rules were configured in preparation step 3.

### 4. Configure the listener and create

1. Listener name: `p01-listener-http-80`; protocol: **HTTP**; port: `80`.
2. Route to the backend set created above. Use a `60` second idle timeout if this setting is shown.
3. For this basic lab, leave optional access/error logging disabled. You can enable it later for troubleshooting.
4. Review the configuration and click **Create load balancer**.
5. Wait for **Active**, then record the public IP. Open **Backend sets → your backend set → Backends** and wait for both backends to report healthy/OK. If needed, use the backend set/listener edit pages to confirm settings the wizard did not expose.

### 5. Test traffic distribution and recovery

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
# Oracle Linux:
sudo systemctl stop httpd
# Ubuntu: use sudo systemctl stop nginx instead.
```

Wait for its health status to become unhealthy, then rerun the requests. Responses should come from the remaining healthy VM. Requests during detection can fail. Restart the service (`sudo systemctl start httpd`, or `nginx` on Ubuntu), wait for healthy status, and verify both names return again.

**Success criteria:** LB Active; both backends healthy after recovery; HTTP responses received through the public address from both VMs.

## Option B - Deployment steps for Terraform

### 1. Prepare Terraform and OCI authentication

Complete **Before you begin**, including the manual security rules. Use a separate working directory/state for this lab; do not reuse the compartment, network, VM, or Console-created LB state.

Install **Terraform 1.5 or newer, below 2.0**. The configuration accepts OCI provider `>= 7.0.0, < 9.0.0`. Run it on a workstation or Cloud Shell with an existing OCI API-key profile in `~/.oci/config`; `config_file_profile` selects that profile. Check its tenancy OCID, user OCID, fingerprint, signing-key path, and permissions. Keep the key outside the repository. Cloud Shell users must configure this profile for this example; the code does not automatically switch to another authentication method.

Files in this lab:

| File | Purpose |
| --- | --- |
| `terraform/versions.tf` | Terraform and provider constraints |
| `terraform/provider.tf` | OCI region and authentication profile |
| `terraform/variables.tf` | Parameter types and validation |
| `terraform/main.tf` | Existing-resource lookups and LB resources |
| `terraform/outputs.tf` | LB address, URL, subnet CIDR, and resolved backends |
| `terraform/terraform.tfvars.example` | All editable attendee parameters |

### 2. Set your parameters

From the extracted `load-balancer` directory:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

1. Replace `compartment_id` with your lab compartment OCID.
2. Confirm `region` and `config_file_profile`.
3. Leave `network_compartment_id` and `backend_compartment_id` null if all resources share the lab compartment; otherwise supply their actual compartment OCIDs. The VCN and LB subnet must be in the same configured network compartment for this example.
4. Confirm the VCN/subnet names and exact VM display names. Change the `p01` prefix consistently if your participant resources use a different prefix.
5. Review bandwidth, backend ports/weights, health check, and listener parameters in this file. Keep the defaults to match Option A.

Values intentionally live in the parameter file, rather than being scattered through resource definitions. A VM must already be running when the plan is created. Multiple attached VNICs are supported; the primary VNIC supplies the backend private address. Existing-resource lookups reject missing or ambiguous names and handle null lists without calling `length(null)`.

### 3. Initialize, validate, and inspect the plan

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out=load-balancer.tfplan
```

Expect **5 resources to add** with the default two backends: one LB, one backend set, two backend entries, and one listener. Existing networks and VMs appear as data-source reads. There should be no changes to them or to security lists. Do not proceed if the selected subnet or backend IPs are wrong. Retain/commit `.terraform.lock.hcl` after initialization to pin the provider used by your training repository.

**Package validation:** Formatting and provider installation were checked with Terraform `1.9.8` and OCI provider `8.29.0`. Provider schema validation was blocked by the build environment's restriction on provider communication sockets. Run the validation and plan commands above in your own environment before deploying. No live OCI plan or deployment was performed while preparing this package.

### 4. Deploy and inspect outputs

```bash
terraform apply load-balancer.tfplan
terraform output
terraform output backend_endpoints
terraform output -raw listener_url
```

The public ephemeral address is requested by creating a public LB without a `reserved_ips` block. Terraform creates the LB configuration; it does not install web servers or verify their HTTP health. Check both backend health statuses in the Console after deployment.

### 5. Test

Run from the Terraform directory:

```bash
LB_URL="$(terraform output -raw listener_url)"
for i in $(seq 1 20); do
  curl --fail --silent --show-error --max-time 10 -H 'Connection: close' "$LB_URL"
  printf '\n'
done
```

Complete the same failure/recovery exercise and success criteria in **Option A, step 5**. Edit `terraform.tfvars` and create a new plan for subsequent changes. Recreate the saved plan after changing parameters or discovering that a backend VM address changed.

## Troubleshooting

| Symptom | What to check / do |
| --- | --- |
| No VCN, subnet, or VM match | Confirm region, exact display name, resource state, compartment OCIDs, and IAM access. Lookups do not search child compartments automatically. |
| More than one matching resource | Give lab resources unique display names within the lookup scope, then update the parameter file. |
| `NotAuthorizedOrNotFound` / 404 | Verify profile tenancy/user, selected region, OCIDs, and permissions across LB, network, and backend compartments. |
| Authentication or signing-key error | Check `~/.oci/config`, profile name, key path, fingerprint, and API key registration. |
| Public LB cannot be created in subnet | Confirm the LB subnet is regional, allows public IPs, and has enough available addresses. This lab uses one regional public subnet; an AD-specific public LB requires two subnets in different ADs. |
| Quota / bandwidth error | Confirm available LB quota and supported bandwidth in the selected region. Use whole Mbps, with minimum no greater than maximum. |
| LB is Active but all backends unhealthy | Confirm server processes, private IPs, port 80 bindings, LB egress, VM ingress, and host firewalls. From a client allowed by your security rules, test each backend's private address directly. |
| Health checks fail with status mismatch | `curl -i http://127.0.0.1/` on the backend should return 200 for `/`. Fix redirects, authentication, virtual-host requirements, or choose a suitable health path/status. |
| Public request times out | Check public LB IP, HTTP URL/port, Internet Gateway route, LB ingress, and any intervening client/proxy firewall. |
| HTTP 502/504 or intermittent errors | Check backend health, response times, listener/backend ports, and application logs. Enable LB error logs if needed. |
| Only one backend page appears | Confirm both backends are healthy with equal weights, pages differ, and no persistence is enabled. Use the curl loop to avoid browser caching effects. |
| Rules disappear after the network lab is applied | Add the intended rules to that lab's Terraform configuration; its state may own the security list. |
| Another operation is already in progress | Wait for the LB work request to finish and retry. If concurrent LB operations repeatedly conflict, use `terraform apply -parallelism=1` after reviewing a fresh plan. |

Inspect the LB's **Work requests**, backend health details, and web-server logs when troubleshooting. Changes to security rules and servers can take time to appear in health status.

## Optional cleanup

### If you used the Console

Delete `p01-lb-01` from the Load Balancer page and confirm deletion. Its listeners, backend set, backend registrations, and ephemeral public IP are removed with it. Backend VMs and the network remain available for other labs.

### If you used Terraform

From this lab's `terraform` directory, with the same state and parameters:

```bash
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
```

Inspect the destroy plan before applying it. The default configuration removes the five lab resources; data sources do not delete the existing VCN, subnet, or VMs. An externally created reserved public IP, if you selected one, is not managed/deleted by this configuration.

For either deployment option, remove only the manual security-list/host-firewall rules added exclusively for this lab when they are no longer needed. If you installed a web server solely for this exercise, stop/disable it or restore the VM's prior configuration. Retain Terraform state securely until cleanup finishes; never commit state or saved plans to GitHub.

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
