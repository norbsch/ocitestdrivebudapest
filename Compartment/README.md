# Compartment Hands-on Lab

**Project:** OCITestDriveBudapest

## Goal / Estimated time

Create an empty OCI compartment to contain the resources from the remaining labs.

**Estimated time:** 5–10 minutes using either deployment option.

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

1. Sign in to the OCI Console in the tenancy provided by your instructor.
2. Confirm that your account can create compartments under the designated parent. Your instructor must arrange compartment management permissions and the resource permissions needed by later labs; this exercise creates no IAM policies.
3. Choose the values below. Use your assigned attendee suffix in the name to avoid collisions.

| Field | Example / instruction |
| --- | --- |
| Parent compartment | Tenancy root, or the existing parent assigned by the instructor |
| Name | `OCITestDriveBudapest-p01` |
| Description | `Resource container for the OCITestDriveBudapest hands-on labs` |
| Optional free-form tag | `Project = OCITestDriveBudapest` |

Use a name of 1–100 characters containing letters, numbers, periods, hyphens, or underscores. Keep the description between 1 and 400 characters. The name must be unique within its parent. Avoid confidential information in names, descriptions, and tags.

Choose **Option A or Option B** for this lab. Both produce the same target configuration. Do not deploy both against the same resources.

For Option B – Terraform, choose one of the following authentication methods and set the parameters in terraform.tfvars:

- Local machine (auth = "APIKey"): Install Terraform CLI and configure an OCI API-signing-key profile in ~/.oci/config. Set oci_config_profile to the profile name, such as "DEFAULT". The profile must contain tenancy, user, fingerprint, and key_file. Register the matching public key with your OCI user and keep the private key outside the repository.

- OCI Cloud Shell (auth = "InstancePrincipal"): Terraform CLI is already installed. Use Cloud Shell’s existing authentication environment; no API-signing-key profile is required. Omit oci_config_profile from terraform.tfvars.

For this lab, set region to your tenancy’s home region. Your OCI user must have permission to create compartments under the selected parent compartment.

## Target configuration

| Setting | Required value |
| --- | --- |
| Resources created | One empty compartment |
| Parent | Existing parent assigned by the instructor, or tenancy root |
| Name | `OCITestDriveBudapest-p01` (use your attendee suffix) |
| Description | `Resource container for the OCITestDriveBudapest hands-on labs` |
| Optional free-form tag | `Project = OCITestDriveBudapest` |
| Result | Active compartment and its OCID |

This lab creates no IAM policies, networking, compute, or database resources. Creating a compartment does not grant access to resources inside it.

## Option A - Deployment steps for OCI Console

### 1. Open the parent compartment

1. Open the navigation menu.
2. Select **Identity & Security**.
3. Under **Identity**, select **Compartments**.
4. For a compartment directly under the tenancy root, choose **Create compartment** from the compartment list. For a nested compartment, first open the designated parent's details, then choose **Create compartment**.

### 2. Create the compartment

1. Enter your **Name** and **Description** from Before you begin.
2. Verify **Parent compartment** carefully. Select the instructor-designated parent if necessary.
3. Optionally add the free-form tag shown above. Follow any tagging requirements imposed by your tenancy.
4. Select **Create compartment**.
5. Open the new compartment and wait for its lifecycle state to become **Active**. Refresh if needed.

### 3. Record and verify the result

1. Check its name and parent on the compartment details page.
2. Find **OCID** and select **Copy**. Record this as the **lab compartment OCID**.
3. In the next lab, select this compartment on every applicable resource creation form. Allow a short propagation delay if it does not immediately appear in a selector, then refresh.

**Success:** one Active compartment exists under the intended parent, and you have its OCID.

Keep the compartment for all remaining labs.

## Option B - Deployment steps for Terraform

Run Terraform commands from this lab’s `terraform/` directory, alongside the existing `.tf` files and `terraform.tfvars.example`.

### 1. Set all lab parameters in one separate file

From this `terraform` directory:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit only `terraform.tfvars` for attendee-specific settings:

| Parameter | What to enter |
| --- | --- |
| `oci_config_profile` | Profile name from `~/.oci/config`, such as `DEFAULT` |
| `home_region` | Your tenancy's home region ID |
| `parent_compartment_ocid` | Existing parent compartment OCID, or tenancy OCID for root |
| `compartment_name` | Your unique name, such as `OCITestDriveBudapest-p01` |
| `compartment_description` | A short, nonblank description |
| `freeform_tags` | Tag map, or `{}` for none |
| `enable_compartment_delete` | Keep `true` for the workshop behavior described below |

All seven inputs are required and have no defaults in `variables.tf`, so editable lab values stay in the parameter file. Provider authentication mode and version constraints are maintained in code.

**Deletion and collision behavior:** `enable_compartment_delete = true` makes the provider reject an existing-name collision and allows Terraform to attempt deletion during destroy. With `false`, the provider can silently adopt a same-named existing compartment and change it; destroy removes it from Terraform state without deleting the OCI compartment. Keep `true` for this lab and review any changes to this setting carefully.

### 2. Initialize, validate, and review a plan

```bash
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out=compartment.tfplan
```

Terraform loads `terraform.tfvars` automatically. Confirm the plan shows **1 to add, 0 to change, 0 to destroy**, with only `oci_identity_compartment.lab`. Check the parent, name, description, and tags. Stop and correct the inputs if the plan differs from what you intend.

### 3. Create and verify the compartment

```bash
terraform apply compartment.tfplan
terraform output
terraform output -raw compartment_ocid
```

Applying the saved plan executes the reviewed changes. Expected result: one compartment, normally with state `ACTIVE`, and its OCID. Verify its parent and name under **Identity & Security → Compartments** in the Console.

Keep the local Terraform state: it tracks ownership for updates and cleanup. Do not commit state, plans, credentials, or attendee parameter files to GitHub. Ensure `.gitignore` excludes state, saved plans, and local `.tfvars` files while retaining the example and provider lock file.

Inspect the plan before applying: import records the resource in state but does not make the configuration match automatically. Import only once and never manage the same compartment from two Terraform states.

Keep attendee settings in `terraform.tfvars`, separate from resource definitions. Keep credentials, private keys, state, and saved plans out of GitHub. Use a separate working directory and state for each lab and attendee.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Invalid OCID validation error | Replace the placeholder with the assigned parent or tenancy OCID. |
| Authentication error | Check the selected profile, key path, fingerprint, registered public key, and tenancy/user OCIDs. |
| Not authorized / not found | Confirm the parent OCID, tenancy, home region, and required IAM access with the instructor. |
| Name collision | Pick a unique attendee name, or deliberately import your own existing compartment under Option B. |
| New compartment missing from selectors | Wait briefly for propagation, then refresh and check permissions. |
| Destroy fails | Remove remaining resources, policies, and child compartments before retrying. |
| Cannot create resources inside the new compartment | Ask the instructor to verify resource permissions; this lab creates no IAM policies. |

## Optional cleanup

Keep the compartment until all other labs are cleaned up.

### Console-created compartment

1. Remove the resources created by the later labs first, preferably using the same tools and Terraform states that created them.
2. Check for remaining resources across regions and any child compartments. The compartment must be empty before deletion; remove any policies attached to it as part of cleanup.
3. Return to **Identity & Security → Compartments** and open the lab compartment.
4. Use its **Delete** action and complete the Console confirmation. Deletion can take time.

### Terraform-managed compartment

First destroy the resources from later labs using their own Terraform configurations, or remove Console-created resources. Check all regions used, attached policies, and child compartments. The compartment must be empty before deletion.

From this compartment lab's `terraform` directory, with the original state and parameter file:

```bash
terraform plan -destroy -out=cleanup.tfplan
terraform apply cleanup.tfplan
```

Confirm the plan targets only your lab compartment. The sample sets `enable_compartment_delete = true`, so the provider attempts actual deletion. Deletion is asynchronous and may take time. If a resource blocks deletion, remove the dependency and review a new destroy plan.

## Oracle documentation references

- [Creating a compartment](https://docs.oracle.com/en-us/iaas/Content/Identity/compartments/To_create_a_compartment.htm)
- [Deleting a compartment](https://docs.oracle.com/en-us/iaas/Content/Identity/compartments/To_delete_a_compartment.htm)
- [Compartment resource and import behavior](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/identity_compartment.html)
- [Configure the OCI provider](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/configuring.htm)
- [Targeting multiple regions and the IAM home region](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/targeting-multiple-regions.htm)
- [Delete a compartment](https://docs.oracle.com/en-us/iaas/Content/Identity/compartments/To_delete_a_compartment.htm)
