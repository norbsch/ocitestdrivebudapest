# Virtual Machines Hands-on Lab

**Project:** OCITestDriveBudapest

## Goal / Estimated time

Create three private Ubuntu Linux VMs in the existing regional VM subnet, sharing one SSH public key. VM 1 in AD1 and VM 2 in AD2 host the web application; VM 3 in AD3 hosts the LLM gateway.

**Estimated time:** 30–45 minutes using OCI Console; 20–30 minutes using Terraform after authentication is configured. Allow additional time for private SSH connectivity if it is not already available.

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

1. Complete the Compartment and Network labs. Record the tenancy OCID, lab compartment OCID, and network compartment OCID. Use the same compartment OCID for the latter two when the VMs and network share a compartment.
2. Sign in to the OCI Console and select the region containing your lab network, normally `eu-frankfurt-1`. It must expose **AD1, AD2, and AD3**. AD names include a tenancy-specific prefix; select entries ending in `AD-1`, `AD-2`, and `AD-3`.
3. Under **Networking → Virtual Cloud Networks**, verify that `p01-vcn` contains `p01-subnet-private-vm` with CIDR `10.0.1.0/24`. It must be **private** and **regional** so it can serve all three ADs.
4. Verify that `10.0.1.2`, `10.0.1.3`, and `10.0.1.4` are unused. OCI reserves `.0`, `.1`, and `.255` in this /24; all three requested addresses are valid.
5. For SSH verification, have a routed private connection (VPN/FastConnect) or an instructor-provided bastion. Applicable security lists/NSGs must allow TCP 22 from that connection's source. A NAT Gateway provides outbound access; it does not provide inbound SSH access.
6. For the Terraform workflow and connection checks, have OpenSSH available on your execution machine.

### 2. Confirm permissions and capacity

Confirm permissions to launch instances and boot volumes, use the existing subnet, and inspect the network, images, and availability domains. Check E5 capacity in all three ADs and limits for **6 OCPUs, 12 GB RAM, and three boot volumes**. Review the estimated cost before launching.

### 3. Choose a deployment option

Choose **Option A - OCI Console** or **Option B - Terraform**. Both options create the target configuration below. Use one option for each lab deployment; do not create the same resources with both options.

Use your assigned attendee prefix in place of `p01`, consistently across all labs. Follow the workshop order: **Compartment → Network → VM → Load Balancer → PostgreSQL → OKE**.

For Option B, follow the two authentication methods in [Prepare the environment and authentication](#2-prepare-the-environment-and-authentication). Keep attendee settings in `terraform.tfvars` and use a separate Terraform directory and state for each lab and attendee.

## Target configuration

### Resource settings

| Setting | VM 1 | VM 2 | VM 3 |
| --- | --- | --- | --- |
| Role | Web application | Web application | LLM gateway |
| Display name | `p01-vm-01` | `p01-vm-02` | `p01-vm-03` |
| Placement | AD1 | AD2 | AD3 |
| Image family | Canonical Ubuntu 24.04 | Same | Same |
| Exact image | `Canonical-Ubuntu-24.04-2026.11.05-0` | Same | Same |
| Shape | `VM.Standard.E5.Flex` | Same | Same |
| OCPUs | 2 | 2 | 2 |
| Memory | 4 GB | 4 GB | 4 GB |
| Existing VCN | `p01-vcn` | Same | Same |
| Existing subnet | `p01-subnet-private-vm` (`10.0.1.0/24`) | Same | Same |
| Primary private IPv4 | `10.0.1.2` (manual) | `10.0.1.3` (manual) | `10.0.1.4` (manual) |
| Public IPv4 | None | None | None |
| Instance metadata | IMDSv2; legacy IMDSv1 disabled | Same | Same |
| SSH key | Generate and save one pair | Reuse VM 1's public key | Reuse VM 1's public key |

Use the standard x86 Ubuntu image `Canonical-Ubuntu-24.04-2026.11.05-0`. Confirm availability in the selected region before the workshop; use an instructor-approved replacement only if necessary.

For other settings not specified here, keep the Console defaults. Terraform leaves optional settings such as boot-volume size, fault domain, launch options, and agent configuration unspecified so OCI chooses its defaults. Optional Console and API defaults can differ; the table above defines the required configuration.

## Option A - Deployment steps for OCI Console

### 1. Start VM 1

1. Open **Compute → Instances** and select the lab compartment.
2. Select **Create instance**.
3. Enter `p01-vm-01` as the name and confirm the compartment.
4. Expand **Placement**, if needed, and select **AD1**. Leave the fault domain and other placement options at their defaults.

Console labels and section order may vary; complete all the sections below before selecting Create.

### 2. Select the image and shape

1. In **Image and shape**, select **Change image**.
2. Select **Ubuntu**, version **24.04**.
3. Open the image-build/version selector, if present, and select `2026.11.05-0`. Confirm the complete image name before continuing.
4. If the build is absent, use its region-specific image OCID from the official image page through the image selector's **Image OCID** option, where available. If OCI rejects it or it is unavailable in your region, ask the instructor which build to use; do not silently select latest.
5. Select **Change shape**. Select the AMD flexible shape **VM.Standard.E5.Flex**.
6. Set **OCPUs to 2** and **memory to 4 GB**. Confirm the shape selection. On this x86 shape, 2 OCPUs correspond to 4 vCPUs; do not enter 4 in the OCPU field.

### 3. Configure the existing network

1. In **Networking**, choose **Select existing virtual cloud network**.
2. Select the network compartment and VCN **p01-vcn**.
3. Choose **Select existing subnet**, select its compartment, and select **p01-subnet-private-vm**.
4. Under **Primary VNIC IP addresses**, select **Manually assign private IPv4 address**.
5. Enter **10.0.1.2**.
6. Confirm no public IPv4 address will be assigned. A private subnet prohibits public IPs; the public-IP control may be hidden or disabled.
7. Leave optional VNIC settings at their defaults. Do not create a new VCN or subnet.

### 4. Generate and save the shared SSH key pair

1. In **Add SSH keys**, select **Generate a key pair for me**.
2. Select **Download private key** and **Download public key**. Save both to a secure local folder before submitting the form.
3. Keep the downloaded filenames together and note their locations. The `.pub` file is the public key to reuse for VM 2 and VM 3; the private key is used by your SSH client.
4. Do not upload the private key to VM 2 or VM 3 or commit either key to the lab repository. OCI cannot recover your private key later.

### 5. Create VM 1

1. Under the available instance/metadata options, require **IMDSv2** and disable legacy IMDSv1 endpoints. Keep **Storage / Boot volume** and other optional settings at their defaults.
2. Review the name, AD1, image build, shape, **2 OCPUs / 4 GB**, subnet, and `10.0.1.2`.
3. Select **Create** and wait for **Running**.
4. In the instance details and primary VNIC details, verify the private IP is `10.0.1.2` and no public IP is present.

### 6. Create VM 2 using the same public key

1. Return to **Compute → Instances → Create instance**.
2. Repeat the configuration above with these changes:

   | Field | Value |
   | --- | --- |
   | Name | `p01-vm-02` |
   | Availability domain | **AD2** |
   | Manually assigned private IPv4 | **10.0.1.3** |
   | Add SSH keys | **Upload public key file (.pub)** |

3. Upload the **public key downloaded for VM 1**. Alternatively, paste that same public key with **Paste public key**. Do not generate another pair.
4. Confirm the same image, E5 shape, **2 OCPUs / 4 GB**, VCN, and subnet.
5. Keep other settings at defaults, select **Create**, and wait for **Running**.
6. Verify AD2, private IP `10.0.1.3`, and no public IP.

### 7. Create VM 3 for the LLM gateway

1. Return to **Compute → Instances → Create instance**.
2. Repeat the VM 1 configuration with these changes:

   | Field | Value |
   | --- | --- |
   | Name | `p01-vm-03` |
   | Availability domain | **AD3** (entry ending in `AD-3`) |
   | Manually assigned private IPv4 | **10.0.1.4** |
   | Add SSH keys | **Upload public key file (.pub)** |

3. Upload the **public key downloaded for VM 1**, or paste that same public key. Do not generate another pair.
4. Confirm Ubuntu 24.04 with the same image build, **VM.Standard.E5.Flex**, **2 OCPUs / 4 GB**, **p01-vcn**, and **p01-subnet-private-vm**. Confirm no public IP will be assigned.
5. Keep other settings at defaults, select **Create**, and wait for **Running**.
6. Verify AD3, private IP `10.0.1.4`, and no public IP. Reserve this VM for the LLM gateway; VM 1 and VM 2 are the web application hosts.

This lab provisions the three VMs. Installing the web application and LLM gateway software is a separate step.

### 8. Verify deployment

Confirm all three VMs are **Running**, match the target configuration, and have no public IP. Then test SSH through your prepared private connection.

Use the same private key for all three VMs. The following commands require an existing routed private connection to the subnet:

```bash
ssh -i ~/.ssh/p01-vm-key ubuntu@10.0.1.2
ssh -i ~/.ssh/p01-vm-key ubuntu@10.0.1.3
ssh -i ~/.ssh/p01-vm-key ubuntu@10.0.1.4
```

For the Console path, substitute the downloaded private-key filename and, on Linux/macOS, restrict it with `chmod 600 /path/to/private-key`. Confirm host-key fingerprints through a trusted channel before accepting them.

If your instructor supplies a jump host, substitute its reachable address, user, and key in your SSH configuration or ProxyJump command. An OCI Bastion managed SSH session uses its own generated connection command and requires its prerequisites and a session for each target. Do not assume these private IPs are reachable directly from your laptop or Cloud Shell.

**Success criteria:** Three private Ubuntu VMs are Running in AD1, AD2, and AD3 at `10.0.1.2`, `10.0.1.3`, and `10.0.1.4`, and SSH works with the shared key.

## Option B - Deployment steps for Terraform

Complete **Before you begin** first. This lab has one README for both deployment options. Run all Terraform commands from `VM/terraform/` in your repository checkout.

### 1. Review the Terraform files

All paths in this table are relative to `VM/terraform/`.

| File | Purpose |
| --- | --- |
| `versions.tf` | Defines the supported Terraform and OCI provider versions. |
| `provider.tf` | Configures the OCI region and selected authentication method. |
| `variables.tf` | Declares input parameters, types, and validation rules. |
| `terraform.tfvars.example` | Provides the example lab settings; copy it to `terraform.tfvars`. |
| `terraform.tfvars` | Contains your local attendee settings; created in step 3 and kept out of Git. |
| `main.tf` | Looks up the existing network and image, then creates three VM instances. |
| `outputs.tf` | Reports instance OCIDs, ADs, private IPs, states, and the selected image OCID. |
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
cd VM/terraform
cp terraform.tfvars.example terraform.tfvars
```

If `terraform.tfvars` already exists, edit that file instead of overwriting it. Set the authentication values from step 2, then review the following lab inputs:

| Parameter | What to enter or check |
| --- | --- |
| `region` | Region containing the network and all three ADs; normally `eu-frankfurt-1`. |
| `tenancy_ocid` | Tenancy OCID used to look up availability domains; needed in both authentication modes. |
| `compartment_ocid`, `network_compartment_ocid` | VM and network compartment OCIDs; use the same OCID when shared. |
| `vcn_name`, `subnet_name` | Exact names of the existing VCN and private regional VM subnet. |
| `image_display_name` | `Canonical-Ubuntu-24.04-2026.11.05-0`, or an instructor-approved compatible image. |
| `shape`, `ocpus`, `memory_in_gbs` | `VM.Standard.E5.Flex`, 2 OCPUs, and 4 GB per VM. |
| `ssh_public_key_path` | Public-key file on the machine running Terraform, such as `~/.ssh/p01-vm-key.pub`. |
| `instances` | Three entries: VM 1 in AD1 at `10.0.1.2`, VM 2 in AD2 at `10.0.1.3`, VM 3 in AD3 at `10.0.1.4`. |

The current example already includes all three VMs. Rename the instance map keys consistently with your attendee prefix. VM 1 and VM 2 host the web application; VM 3 is reserved for the LLM gateway. The configuration requires exactly three instances with distinct private IPs.

#### Prepare the shared SSH key

Generate one key pair before planning, or reuse the intended existing lab key. In Linux/macOS, Cloud Shell, or a compatible Bash shell:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t rsa -b 4096 -f ~/.ssh/p01-vm-key -C "OCITestDriveBudapest"
chmod 600 ~/.ssh/p01-vm-key
```

Choose a passphrase when prompted. If the file already exists, reuse it or choose a different filename; do not overwrite a key you need. On Windows, run `ssh-keygen` in PowerShell and use your Windows home path for `ssh_public_key_path`; Terraform strings accept forward slashes.

All three instances use the same `.pub` file. Terraform reads only the public key. Keep the private key outside the repository and available to your SSH client. If Terraform and SSH run on different machines, copy only the public key to the Terraform machine.

The VM SSH key and the OCI API signing key serve different purposes. Cloud Shell authentication removes the need to supply an API signing key; it does not remove the need for a VM SSH key.

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

For a new deployment, expect **3 to add, 0 to change, 0 to destroy**: three Compute instance resources. Boot volumes and primary VNICs are created with the instances. When extending a previous two-VM deployment using its existing state, expect only the third VM to be added if the first two configurations are unchanged.

Verify the names, ADs, image, shape, OCPU/memory settings, private IPs, `assign_public_ip = false`, and IMDSv2 setting. The existing VCN and subnet are read through data sources. OCI checks IP availability, quotas, and launch capacity during creation.

Review the complete plan before applying. Stop if it includes unexpected changes or deletions. If you edit parameters after saving the plan, create and review a new plan.

### 6. Apply the reviewed plan

```bash
terraform apply lab.tfplan
terraform output
```

Applying a saved plan executes its reviewed changes without a second approval prompt. Wait for completion and keep the Terraform state for later updates and cleanup. If an apply only partially succeeds, retain the state, resolve the error, and create a fresh plan.

### 7. Verify deployment

```bash
terraform output instances
terraform output -raw image_id
```

1. In **Compute → Instances**, confirm all three VMs are **Running** with the expected ADs, private IPs, image, and shape settings.
2. Confirm no VM has a public IP and all three use the same SSH public key.
3. Follow [Option A, step 8](#8-verify-deployment) to test private SSH access using the matching private key.

**Success criteria:** VM 1 is in AD1 at `10.0.1.2`, VM 2 is in AD2 at `10.0.1.3`, and VM 3 is in AD3 at `10.0.1.4`; all three are Running and reachable through the prepared private SSH path.

### 8. Update the configuration

Edit `terraform.tfvars` for routine changes, then repeat steps 4–7 with the same working directory and state. Generate a new plan each time. Avoid editing Terraform-managed resources directly in the Console, and never manage the same resource from two Terraform states.

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
| AD2 or AD3 absent | Use a region with at least three ADs and recreate the prerequisite network there if necessary. Keep VM 1 in AD1, VM 2 in AD2, and VM 3 in AD3. |
| Out of host capacity | Retry later or ask the instructor to approve a placement/shape change. |
| Image not found | Verify the exact image name, region, and E5 compatibility. Check the official image page for a regional OCID. Change the configured image only with an intentional workshop decision. |
| VCN/subnet lookup fails | Verify region, network compartment, exact display names, permissions, and duplicate names. |
| Subnet unavailable in AD2 or AD3 | Confirm it is regional; an AD1-specific subnet cannot be shared across ADs. |
| IP already in use | Remove the conflicting lab deployment or choose an approved unused IP. Do not run both procedures against the same IPs. |
| Terraform cannot read key file | Generate the key before planning and check the `.pub` path on the Terraform execution machine. |
| SSH timeout | Verify private routing, bastion/session status, TCP 22 security rules, and guest SSH service. NAT alone is insufficient. |
| Permission denied (publickey) | Use user `ubuntu` and the private key matching the public key installed at creation. |
| `Invalid instanceOptions.areLegacyImdsEndpointsDisabled: false` / `imds-disable-v1` | The tenancy prohibits IMDSv1. Require IMDSv2 in the Console. The current Terraform source already sets `instance_options.are_legacy_imds_endpoints_disabled = true`; use the current source then review and apply a fresh plan. |

If a VCN/subnet lookup returns `Invalid function argument` for `length(null)`, verify the region, network compartment, exact names, and IAM access first. The current VM lookup conditions call `length` directly; a null-safe condition such as `try(length(self.virtual_networks), 0) == 1` (and the equivalent for `self.subnets`) provides a clearer missing-resource diagnostic.

## Optional cleanup

Clean up the load balancer and any workloads using these VMs before terminating them. Use the same deployment option that created each resource.

### Option A - OCI Console

1. Remove load balancer backend dependencies and stop any application work using the VMs.
2. Under **Compute → Instances**, select each of the three lab VMs and choose **Terminate**.
3. Enable boot-volume deletion if you no longer need those volumes.
4. Review any separately attached or preserved block volumes; retain the shared network and compartment for other labs.

### Option B - Terraform

From `VM/terraform/`, use the original state and parameter file. Create a cleanup plan:

```bash
terraform plan -destroy -out=cleanup.tfplan
terraform show cleanup.tfplan
```

Confirm the plan removes only this lab's three instances. Their boot volumes are deleted by the provider's default termination behavior. Review manually attached or separately preserved volumes independently.

After reviewing the plan, apply it:

```bash
terraform apply cleanup.tfplan
```

Keep Terraform state until cleanup is confirmed. Delete shared network resources and the compartment only after all dependent labs are finished.

## Oracle documentation references

- [Creating an instance](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm)
- [Ubuntu 24.04 image catalog and regional OCIDs](https://docs.oracle.com/en-us/iaas/images/ubuntu-2404/)
- [Compute shapes](https://docs.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm)
- [Managing SSH key pairs](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/managingkeypairs.htm)
- [VCNs and subnets, including reserved addresses](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/Overview_of_VCNs_and_Subnets.htm)
- [Terraform: instance resource](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/core_instance.html)
- [Terraform: image data source](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/d/core_images.html)
- [Terraform: AD lookup by AD number](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/d/identity_availability_domain.html)
- [OCI Terraform provider configuration and authentication](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/configuring.htm)
- [Using OCI Cloud Shell](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/devcloudshellgettingstarted.htm)
- [OCI SDK and CLI configuration file](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
