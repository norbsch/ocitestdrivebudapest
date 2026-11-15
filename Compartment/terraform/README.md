# Create a compartment using Terraform

## 1. Prepare your workstation and access

Install Terraform CLI 1.5 or later (below 2.0). This configuration uses the Oracle OCI provider 7.x. `terraform init` selects a compatible release; retain and commit `.terraform.lock.hcl` so attendees use the reviewed version.

Obtain permission to create a compartment under the assigned parent. Arrange resource permissions for later labs with your instructor separately. No IAM policy is created here.

Configure an OCI API-signing-key profile in `~/.oci/config`, using Oracle's [provider configuration guide](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/configuring.htm). The profile must include `tenancy`, `user`, `fingerprint`, and `key_file`; register the matching public key with your OCI user. Use an absolute private-key path. Keep credentials, any key passphrase, and private keys outside this repository. This lab uses API-key authentication, not a Cloud Shell security-token session.

Identify your tenancy's **home region**, the existing **parent compartment OCID** (or tenancy OCID for root), and a unique attendee compartment name.

Choose this path or the [Console path](../CONSOLE_GUIDE.md). To manage a compartment already created in the Console, use step 6 before planning a creation.

## 2. Set all lab parameters in one separate file

From this `terraform` directory:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit only `terraform.tfvars` for attendee-specific settings:

| Parameter | What to enter |
| --- | --- |
| `oci_config_profile` | Profile name from `~/.oci/config`, such as `DEFAULT` |
| `home_region` | Your tenancy's home region ID; the example is illustrative |
| `parent_compartment_ocid` | Existing parent compartment OCID, or tenancy OCID for root |
| `compartment_name` | Your unique name, such as `OCITestDriveBudapest-alice-01` |
| `compartment_description` | A short, nonblank description |
| `freeform_tags` | Tag map, or `{}` for none |
| `enable_compartment_delete` | Keep `true` for the workshop behavior described below |

All seven inputs are required and have no defaults in `variables.tf`, so editable lab values stay in the parameter file. Provider authentication mode and version constraints are maintained in code.

**Deletion and collision behavior:** `true` makes the provider reject an existing-name collision and allows Terraform to attempt deletion during destroy. With `false`, the provider can silently adopt a same-named existing compartment and change it; destroy removes it from Terraform state without deleting the OCI compartment. Keep `true` for this lab and review any changes to this setting carefully.

## 3. Initialize, validate, and review a plan

```bash
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out=compartment.tfplan
```

Terraform loads `terraform.tfvars` automatically. Confirm the plan shows **1 to add, 0 to change, 0 to destroy**, with only `oci_identity_compartment.lab`. Check the parent, name, description, and tags. Stop and correct the inputs if the plan differs from what you intend.

## 4. Create and verify the compartment

```bash
terraform apply compartment.tfplan
terraform output
terraform output -raw compartment_ocid
```

Applying the saved plan executes the reviewed changes. Expected result: one compartment, normally with state `ACTIVE`, and its OCID. Verify its parent and name under **Identity & Security → Compartments** in the Console.

Keep the local Terraform state: it tracks ownership for updates and cleanup. Do not commit state, plans, credentials, or attendee parameter files to GitHub. The included `.gitignore` excludes state, plans using the `.tfplan` extension, and `.tfvars` files while retaining the example and provider lock file.

## 5. Continue with the networking lab

Copy the value from `terraform output -raw compartment_ocid` into the **networking lab's own parameter file**, using its existing resource-compartment variable name. Do not reuse `parent_compartment_ocid`: that input identifies where this compartment is created, not where the next lab's resources belong.

Run the networking lab in its own directory and state. It will create the VCN, subnets, and gateways later; this configuration creates only the compartment. Keep this compartment until all subsequent labs are finished.

## 6. Optional: adopt a compartment you created in the Console

Skip this step for a new Terraform-created compartment. For a compartment you own and intend to manage here:

1. Configure `terraform.tfvars` to match that compartment's parent, name, description, and tags.
2. Run `terraform init` if not already done.
3. Replace the placeholder below with its **actual compartment OCID**, then import:

```bash
terraform import oci_identity_compartment.lab 'REPLACE_WITH_EXISTING_LAB_COMPARTMENT_OCID'
terraform plan
```

Inspect the plan before applying: import records the resource in state but does not make the configuration match automatically. Import only once and never manage the same compartment from two Terraform states.

## 7. Optional cleanup after the full training

First destroy the resources from later labs using their own Terraform configurations, or remove Console-created resources. Check all regions used, attached policies, and child compartments. The compartment must be empty before deletion.

From this compartment lab's `terraform` directory, with the original state and parameter file:

```bash
terraform plan -destroy -out=cleanup.tfplan
terraform apply cleanup.tfplan
```

Confirm the plan targets only your lab compartment. The sample sets `enable_compartment_delete = true`, so the provider attempts actual deletion. Deletion is asynchronous and may take time. If a resource blocks deletion, remove the dependency and review a new destroy plan.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Invalid OCID validation error | Replace the placeholder with the assigned parent or tenancy OCID. |
| Authentication error | Check the selected profile, key path, fingerprint, registered public key, and tenancy/user OCIDs. |
| Not authorized / not found | Confirm the parent OCID, tenancy, home region, and required IAM access with the instructor. |
| Name collision | Pick a unique attendee name, or deliberately import your own existing compartment using step 6. |
| New compartment missing from selectors | Wait briefly for propagation, then refresh and check permissions. |
| Destroy fails | Remove remaining resources, policies, and child compartments before retrying. |

## Oracle references

- [Compartment resource and import behavior](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/identity_compartment.html)
- [Configure the OCI provider](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/configuring.htm)
- [Targeting multiple regions and the IAM home region](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/targeting-multiple-regions.htm)
- [Delete a compartment](https://docs.oracle.com/en-us/iaas/Content/Identity/compartments/To_delete_a_compartment.htm)
