# Virtual Machines Hands-on Lab

**Project:** OCITestDriveBudapest

## Goal / Estimated time

Create two private Ubuntu Linux VMs in the existing regional VM subnet, one in AD1 and one in AD2, sharing one SSH public key.

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

1. Sign in to OCI and select the region containing your existing lab network. The region must expose **AD1 and AD2**, with E5 capacity in both. AD names include a tenancy-specific prefix; select the entries ending in `AD-1` and `AD-2`.
2. Select the compartment created in the earlier lab. You need permissions to launch instances and boot volumes, use the existing subnet, and inspect the network, images, and availability domains. Ask the instructor to resolve missing access.
3. Under **Networking → Virtual cloud networks**, open `p01-vcn` and verify that `p01-subnet-private-vm` has CIDR `10.0.1.0/24`, is **private**, and is **regional**. An AD-specific subnet cannot serve both requested ADs.
4. Verify that `10.0.1.2` and `10.0.1.3` are unused. OCI reserves the first two and last addresses of a subnet; for this /24, those are `.0`, `.1`, and `.255`. Both requested addresses are valid.
5. Allow for the cost of two E5 instances and their boot volumes. Review your tenancy limits and estimate before launching.
6. For SSH verification, have a routed private connection (VPN/FastConnect) or an instructor-provided bastion. Applicable security lists/NSGs must allow TCP 22 from that connection's source. A NAT gateway provides outbound access; it does not provide inbound SSH access.

Choose **Option A or Option B** for this lab. Both produce the same target configuration. Do not deploy both against the same resources. Run the labs in order: **Compartment → Networking → Virtual Machines**.

Use your attendee prefix in place of `p01`, matching the networking lab. For Option B, install Terraform CLI **1.5 or later, below 2.0**, and OpenSSH.

## Target configuration

| Setting | VM 1 | VM 2 |
| --- | --- | --- |
| Display name | `p01-vm-01` | `p01-vm-02` |
| Placement | AD1 | AD2 |
| Image family |  Canonical Ubuntu 24.04 | Canonical Ubuntu 24.04 |
| Exact image | `Canonical-Ubuntu-24.04-2026.11.05-0` | Same |
| Shape | `VM.Standard.E5.Flex` | Same |
| OCPUs | 2 | 2 |
| Memory | 4 GB | 4 GB |
| Existing VCN | `p01-vcn` | Same |
| Existing subnet | `p01-subnet-private-vm` (`10.0.1.0/24`) | Same |
| Primary private IPv4 | `10.0.1.2` (manual) | `10.0.1.3` (manual) |
| Public IPv4 | None | None |
| Metadata service | Require IMDSv2; disable IMDSv1 | Same |
| SSH key | Generate and save one pair | Reuse VM 1's public key |

Use the standard x86 image `Oracle-Linux-9.8-2026.10.30-0`. Confirm availability in the selected region before the workshop; use an instructor-approved replacement only if necessary.

Require **IMDSv2** for both instances; disable legacy IMDSv1 endpoints. For other settings not specified here, keep the Console defaults. Terraform leaves optional settings such as boot-volume size, fault domain, launch options, and agent configuration unspecified so OCI chooses its defaults. Optional Console and API defaults can differ; the table above defines the required configuration.

## Option A - Deployment steps for OCI Console

### 1. Start VM 1

1. Open **Compute → Instances** and select the lab compartment.
2. Click **Create instance**.
3. Enter `p01-vm-01` as the name and confirm the compartment.
4. Expand **Placement**, if needed, and select **AD1**. Leave the fault domain and other placement options at their defaults.

Console labels and section order may vary; complete all the sections below before selecting Create.

### 2. Select the image and shape

1. In **Image and shape**, click **Change image**.
2. Select **Ubuntu**, version **24.04**.
3. Open the image-build/version selector, if present, and select `2026.11.05-0`. Confirm the complete image name before continuing.
4. If the build is absent, use its region-specific image OCID from the official image page through the image selector's **Image OCID** option, where available. If OCI rejects it or it is unavailable in your region, ask the instructor which build to use; do not silently select latest.
5. Click **Change shape**. Select the AMD flexible shape **VM.Standard.E5.Flex**.
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
2. Click **Download private key** and **Download public key**. Save both to a secure local folder before submitting the form.
3. Keep the downloaded filenames together and note their locations. The `.pub` file is the public key to reuse for VM 2; the private key is used by your SSH client.
4. Do not upload the private key to VM 2 or commit either key to the lab repository. OCI cannot recover your private key later.

### 5. Create VM 1

1. In the instance metadata/security settings, enable **Require IMDSv2** (disable legacy IMDSv1 endpoints). Apply the same setting for VM 2. Keep **Storage / Boot volume** and other optional settings at their defaults.
2. Review the name, AD1, image build, shape, **2 OCPUs / 4 GB**, subnet, and `10.0.1.2`.
3. Click **Create** and wait for **Running**.
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
5. Keep other settings at defaults, click **Create**, and wait for **Running**.
6. Verify AD2, private IP `10.0.1.3`, and no public IP.

## Option B - Deployment steps for Terraform

Run Terraform commands from this lab’s `terraform/` directory, alongside the existing `.tf` files and `terraform.tfvars.example`. Keep this README at the lab root. This document consolidates the supplied guides; the Terraform source files are maintained separately and are required for Option B.

### 1. Prepare authentication and tooling

1. Install Terraform CLI **1.5 or newer, below 2.0**, plus OpenSSH (`ssh-keygen`).
2. Configure OCI API-key authentication in `~/.oci/config` (for example using `oci setup config`). The profile must include your user, tenancy, fingerprint, API signing key path, and region. The API signing key authenticates Terraform; it is separate from the VM SSH key below.
3. Obtain the tenancy OCID, lab compartment OCID, and network compartment OCID. If the network and VMs share a compartment, use the same compartment OCID for both inputs.
4. Open a terminal in this lab's `terraform/` directory.

### 2. Generate one SSH key pair for both VMs

Before planning VM 1, generate one local RSA key pair. The Console can generate a key interactively; the Terraform workflow generates it locally and supplies only its public half to OCI.

Linux/macOS or a compatible shell:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t rsa -b 4096 -f ~/.ssh/p01-vm-key -C "OCITestDriveBudapest"
chmod 600 ~/.ssh/p01-vm-key
```

Choose a passphrase when prompted. If the path already exists, reuse the intended existing lab key or choose a new filename; do not overwrite a key you need. On Windows, run `ssh-keygen` in PowerShell and use your Windows home path for `ssh_public_key_path` (forward slashes are accepted in Terraform strings).

Both instances reference this one `.pub` file. The private key is never read by Terraform and is not generated into Terraform state. Generate the key on the machine where Terraform runs, or securely make only the public key available there before planning. Do not put private keys in this repository.

### 3. Set all parameters in a separate file

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit **terraform.tfvars**:

- Replace all three placeholder OCIDs.
- Set `region` to the region containing the existing network and both ADs. The example uses `eu-frankfurt-1`.
- Set `config_file_profile` to your OCI profile name.
- Confirm `vcn_name`, `subnet_name`, and the exact image display name.
- Confirm the SSH public-key path.
- Keep the two default instance entries, or change the ADs, IPs, and names if instructed.

All attendee-editable infrastructure parameters are in this file; `variables.tf` defines their types. Authentication material remains in your OCI profile. No edits to `main.tf` are required. VCN and subnet display names must each identify exactly one matching resource in the configured scope. This lab assumes the VCN and subnet are in the same network compartment.

### 4. Initialize and validate

```bash
terraform init
terraform fmt -check
terraform validate
```

The provider constraint supports OCI provider major versions 7 and 8. Initialization records the selected provider in `.terraform.lock.hcl`; commit that lock file to GitHub for repeatable workshop runs. Retain the reviewed lock file supplied with the Terraform source when publishing the lab; this README does not establish which provider version your checkout locks.

### Require IMDSv2

Before planning, confirm that each instance resource contains the following block. This is a source correction for a missing setting; routine attendee changes remain in `terraform.tfvars`. If the source exposes this setting as a variable, set that variable to `true` in the parameter file instead.

```hcl
instance_options {
  are_legacy_imds_endpoints_disabled = true
}
```

### 5. Review the plan

```bash
terraform plan -out=vm-lab.tfplan
```

Expect **2 resources to add**: two `oci_core_instance.vm` resources. Their boot volumes and primary VNICs are created with the instances. The existing compartment, VCN, and subnet are read as inputs and are not created or changed.

Check the names, ADs, image, shape configuration, private IPs, and `assign_public_ip = false`. The image is looked up by its exact name and shape compatibility in your selected region. The plan stops if the VCN, subnet, or image is not uniquely found, the subnet is not regional/private, or an IP is outside the subnet or reserved. OCI checks IP availability, quota, and launch capacity when creating the instances.

### 6. Apply

```bash
terraform apply vm-lab.tfplan
terraform output instances
```

Both VMs may launch concurrently and use the same public key. Generating a new key for the second VM is unnecessary. Inspect the output and OCI Console to confirm both are **Running** with the expected ADs and private IPs.

### Terraform files

| File | Purpose |
| --- | --- |
| `versions.tf` | Terraform and OCI provider requirements |
| `provider.tf` | Region and OCI profile |
| `variables.tf` | Input definitions and validation |
| `terraform.tfvars.example` | All attendee settings; copy to `terraform.tfvars` |
| `main.tf` | Existing-resource lookups and two VM resources |
| `outputs.tf` | Instance IDs, placement, private IPs, states, and image OCID |

### Verify SSH access (either deployment option)

Use the same private key for both VMs. The following commands require an existing routed private connection to the subnet:

```bash
ssh -i ~/.ssh/p01-vm-key opc@10.0.1.2
ssh -i ~/.ssh/p01-vm-key opc@10.0.1.3
```

For the Console path, substitute the downloaded private-key filename and, on Linux/macOS, restrict it with `chmod 600 /path/to/private-key`. Confirm host-key fingerprints through a trusted channel before accepting them.

If your instructor supplies a jump host, substitute its reachable address, user, and key in your SSH configuration or ProxyJump command. An OCI Bastion managed SSH session uses its own generated connection command and requires its prerequisites and a session for each target. Do not assume these private IPs are reachable directly from your laptop or Cloud Shell.

Keep attendee settings in `terraform.tfvars`, separate from resource definitions. Keep credentials, private keys, state, and saved plans out of GitHub. Commit the Terraform source, sanitized example parameters, and reviewed `.terraform.lock.hcl`. Use a separate working directory and state for each lab and attendee.

**Validation scope:** Only README files were supplied for this update. The Terraform source and a live OCI deployment were not validated during standardization. Run the checks and review the plan in your workshop environment.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| AD2 absent | Use a region with at least two ADs and recreate the prerequisite network there if necessary. Do not silently place both VMs in AD1. |
| Out of host capacity | Retry later or ask the instructor to approve a placement/shape change. |
| Image not found | Verify the exact image name, region, and E5 compatibility. Check the official image page for a regional OCID. Change the configured image only with an intentional workshop decision. |
| VCN/subnet lookup fails | Verify region, network compartment, exact display names, permissions, and duplicate names. |
| Subnet unavailable in AD2 | Confirm it is regional; an AD1-specific subnet cannot be shared across ADs. |
| IP already in use | Remove the conflicting lab deployment or choose an approved unused IP. Do not run both procedures against the same IPs. |
| Terraform cannot read key file | Generate the key before planning and check the `.pub` path on the Terraform execution machine. |
| SSH timeout | Verify private routing, bastion/session status, TCP 22 security rules, and guest SSH service. NAT alone is insufficient. |
| Permission denied (publickey) | Use user `opc` and the private key matching the public key installed at creation. |
| Apply partially succeeds | Keep the state, resolve the reported failure, then create a fresh plan and apply it. Do not delete state or recreate an already managed VM manually. |
| `Invalid instanceOptions.areLegacyImdsEndpointsDisabled: false` / `imds-disable-v1` | The tenancy prohibits IMDSv1. Require IMDSv2 in the Console, or set `instance_options.are_legacy_imds_endpoints_disabled = true` in Terraform as shown above, then review and apply a fresh plan. |

## Optional cleanup

For **Terraform-created instances**, from the same directory, using the same state and inputs:

```bash
terraform plan -destroy -out=vm-lab-destroy.tfplan
terraform apply vm-lab-destroy.tfplan
```

Review that only this lab's two instances are removed. Boot volumes created with these instances are deleted by the provider's default termination behavior. Any manually attached or separately preserved volumes require separate review.

For **Console-created instances**, select each instance under **Compute → Instances**, choose **Terminate**, and enable deletion of its boot volume if no longer needed. Review remaining block volumes. Keep the prerequisite compartment and networking until all dependent labs are finished.

Keep Terraform state until cleanup succeeds. Ensure `.gitignore` excludes state, local variable files, plans, and common key filenames. Commit the source and provider lock file; never commit credentials or SSH private keys. If you choose a custom key filename, keep it outside the repository.

## Oracle documentation references

- [Creating an instance](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm)
- [Ubuntu 24.04 image catalog and regional OCIDs](https://docs.oracle.com/en-us/iaas/images/ubuntu-2404/)
- [Compute shapes](https://docs.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm)
- [Managing SSH key pairs](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/managingkeypairs.htm)
- [VCNs and subnets, including reserved addresses](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/Overview_of_VCNs_and_Subnets.htm)
- [Terraform: instance resource](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/core_instance.html)
- [Terraform: image data source](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/d/core_images.html)
- [Terraform: AD lookup by AD number](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/d/identity_availability_domain.html)
