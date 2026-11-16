# Lab: Create two private OCI virtual machines

Part of **OCITestDriveBudapest**. This lab builds on the compartment and networking labs. Create two Oracle Linux instances in the existing private VM subnet, with one instance in each of two availability domains and the same SSH public key on both.

Choose **either the Console procedure or Terraform procedure**. Running both with the default addresses will cause an IP conflict. No instances have been deployed by this guide.

## Target configuration

| Setting | VM 1 | VM 2 |
| --- | --- | --- |
| Display name | `p01-vm-01` | `p01-vm-02` |
| Placement | AD1 | AD2 |
| Image family | Oracle Linux 9 | Oracle Linux 9 |
| Exact image | `Oracle-Linux-9.8-2026.10.30-0` | Same |
| Shape | `VM.Standard.E5.Flex` | Same |
| OCPUs | 2 | 2 |
| Memory | 4 GB | 4 GB |
| Existing VCN | `p01-vcn` | Same |
| Existing subnet | `p01-subnet-private-vm` (`10.0.1.0/24`) | Same |
| Primary private IPv4 | `10.0.1.2` (manual) | `10.0.1.3` (manual) |
| Public IPv4 | None | None |
| SSH key | Generate and save one pair | Reuse VM 1's public key |

Oracle lists the requested image build as **Oracle Linux 9.8**, released November 4, 2026. Use the standard x86 image, rather than an Arm or GPU variant. Exact image availability must be checked in the selected region.

Unless this guide explicitly changes a setting, keep the Console defaults. Terraform leaves optional settings such as boot-volume size, fault domain, launch options, and agent configuration unspecified so OCI chooses its defaults. Optional Console and API defaults can differ; the table above defines the required configuration.

## Before you begin

1. Sign in to OCI and select the region containing your existing lab network. The region must expose **AD1 and AD2**, with E5 capacity in both. AD names include a tenancy-specific prefix; select the entries ending in `AD-1` and `AD-2`.
2. Select the compartment created in the earlier lab. You need permissions to launch instances and boot volumes, use the existing subnet, and inspect the network, images, and availability domains. Ask the instructor to resolve missing access.
3. Under **Networking → Virtual cloud networks**, open `p01-vcn` and verify that `p01-subnet-private-vm` has CIDR `10.0.1.0/24`, is **private**, and is **regional**. An AD-specific subnet cannot serve both requested ADs.
4. Verify that `10.0.1.2` and `10.0.1.3` are unused. OCI reserves the first two and last addresses of a subnet; for this /24, those are `.0`, `.1`, and `.255`. Both requested addresses are valid.
5. Allow for the cost of two E5 instances and their boot volumes. Review your tenancy limits and estimate before launching.
6. For SSH verification, have a routed private connection (VPN/FastConnect) or an instructor-provided bastion. Applicable security lists/NSGs must allow TCP 22 from that connection's source. A NAT gateway provides outbound access; it does not provide inbound SSH access.

## Option A: OCI Console

### 1. Start VM 1

1. Open **Compute → Instances** and select the lab compartment.
2. Click **Create instance**.
3. Enter `p01-vm-01` as the name and confirm the compartment.
4. Expand **Placement**, if needed, and select **AD1**. Leave the fault domain and other placement options at their defaults.

Console labels and section order may vary; complete all the sections below before selecting Create.

### 2. Select the image and shape

1. In **Image and shape**, click **Change image**.
2. Select **Oracle Linux**, version **9** (9.8 where a minor version is shown).
3. Open the image-build/version selector, if present, and select `Oracle-Linux-9.8-2026.10.30-0`. Confirm the complete image name before continuing.
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

1. Keep **Storage / Boot volume** and other optional settings at their defaults.
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

## Option B: Terraform

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

The provider constraint supports OCI provider major versions 7 and 8. Initialization records the selected provider in `.terraform.lock.hcl`; commit that lock file to GitHub for repeatable workshop runs. The included lock file pins OCI provider 8.29.0. Retain it when publishing the lab.

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

## Verify SSH access

Use the same private key for both VMs. The following commands require an existing routed private connection to the subnet:

```bash
ssh -i ~/.ssh/p01-vm-key opc@10.0.1.2
ssh -i ~/.ssh/p01-vm-key opc@10.0.1.3
```

For the Console path, substitute the downloaded private-key filename and, on Linux/macOS, restrict it with `chmod 600 /path/to/private-key`. Confirm host-key fingerprints through a trusted channel before accepting them.

If your instructor supplies a jump host, substitute its reachable address, user, and key in your SSH configuration or ProxyJump command. An OCI Bastion managed SSH session uses its own generated connection command and requires its prerequisites and a session for each target. Do not assume these private IPs are reachable directly from your laptop or Cloud Shell.

After logging in, run:

```bash
cat /etc/oracle-release
lscpu
free -h
hostname -I
```

Expect Oracle Linux 9.8, 4 logical CPUs for 2 E5 OCPUs, approximately 4 GB installed memory (usable memory is lower), and the assigned private IP. The OS release confirms the OS version; use the Console image details or Terraform's `image_id` output to verify the exact launch image build. Exit VM 1 before connecting to VM 2.

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

## Clean up

For **Terraform-created instances**, from the same directory, using the same state and inputs:

```bash
terraform plan -destroy -out=vm-lab-destroy.tfplan
terraform apply vm-lab-destroy.tfplan
```

Review that only this lab's two instances are removed. Boot volumes created with these instances are deleted by the provider's default termination behavior. Any manually attached or separately preserved volumes require separate review.

For **Console-created instances**, select each instance under **Compute → Instances**, choose **Terminate**, and enable deletion of its boot volume if no longer needed. Review remaining block volumes. Keep the prerequisite compartment and networking until all dependent labs are finished.

Keep Terraform state until cleanup succeeds. The supplied `.gitignore` excludes state, local variable files, plans, and common key filenames. Commit the source and provider lock file; never commit credentials or SSH private keys. If you choose a custom key filename, keep it outside the repository.

## Official references

- [Creating an instance](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/launchinginstance.htm)
- [Oracle Linux 9.8 image: 2026.10.30-0](https://docs.oracle.com/en-us/iaas/images/oracle-linux-9x/oracle-linux-9-8-2026-10-30-0.htm)
- [Compute shapes](https://docs.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm)
- [Managing SSH key pairs](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/managingkeypairs.htm)
- [VCNs and subnets, including reserved addresses](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/Overview_of_VCNs_and_Subnets.htm)
- [Terraform: instance resource](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/core_instance.html)
- [Terraform: image data source](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/d/core_images.html)
- [Terraform: AD lookup by AD number](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/d/identity_availability_domain.html)

## Validation scope

Checked with Terraform CLI 1.9.8: `terraform fmt -check` passed and `terraform init -backend=false` installed OCI provider 8.29.0. Input references were also checked. Full `terraform validate` was blocked by a provider startup/handshake failure in the authoring environment; provider-schema validation is therefore incomplete. No live OCI plan or apply was run. Run the validation and plan steps above in your workshop environment before use; a plan requires your configured OCI access, and regional capacity remains subject to availability.
