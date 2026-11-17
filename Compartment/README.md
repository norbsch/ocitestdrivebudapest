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

### 1. Confirm the prerequisites

1. Sign in to the [OCI Console](https://cloud.oracle.com/) in the tenancy provided by your instructor.
2. Select your tenancy's **home region** for this compartment lab.
3. Identify the parent compartment assigned by the instructor, or use the tenancy root.
4. Choose the values below. Use your attendee suffix to avoid name collisions.

| Field | Example / instruction |
| --- | --- |
| Parent compartment | Tenancy root, or the existing parent assigned by the instructor |
| Name | `OCITestDriveBudapest-p01` |
| Description | `Resource container for the OCITestDriveBudapest hands-on labs` |
| Optional free-form tag | `Project = OCITestDriveBudapest` |

Use a name of 1–100 characters containing letters, numbers, periods, hyphens, or underscores. Keep the description between 1 and 400 characters. The name must be unique within its parent. Avoid confidential information in names, descriptions, and tags.

### 2. Confirm permissions and capacity

Confirm that your account can create compartments under the designated parent. Your instructor must arrange compartment management permissions and the resource permissions needed by later labs. This lab creates no IAM policies, and creating a compartment does not grant access to resources inside it.

### 3. Choose a deployment option

Choose **Option A - OCI Console** or **Option B - Terraform**. Both options create the target configuration below. Use one option for each lab deployment; do not create the same resources with both options.

Use your assigned attendee prefix in place of `p01`, consistently across all labs. Follow the workshop order: **Compartment → Network → VM → Load Balancer → PostgreSQL → OKE**.

For Option B, follow the two authentication methods in [Prepare the environment and authentication](#2-prepare-the-environment-and-authentication). Keep attendee settings in `terraform.tfvars` and use a separate Terraform directory and state for each lab and attendee.

## Target configuration

### Resource settings

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

1. Enter your **Name** and **Description** from **Before you begin**.
2. Verify **Parent compartment** carefully. Select the instructor-designated parent if necessary.
3. Optionally add the free-form tag shown above. Follow any tagging requirements imposed by your tenancy.
4. Select **Create compartment**.
5. Open the new compartment and wait for its lifecycle state to become **Active**. Refresh if needed.

### 3. Verify deployment

1. Check its name and parent on the compartment details page.
2. Find **OCID** and select **Copy**. Record this as the **lab compartment OCID**.
3. In the next lab, select this compartment on every applicable resource creation form. Allow a short propagation delay if it does not immediately appear in a selector, then refresh.

**Success criteria:** one Active compartment exists under the intended parent, and you have its OCID.

Keep the compartment for all remaining labs.

## Option B - Deployment steps for Terraform

Complete **Before you begin** first. This lab has one README for both deployment options. Run all Terraform commands from `Compartment/terraform/` in your repository checkout.

### 1. Review the Terraform files

All paths in this table are relative to `Compartment/terraform/`.

| File | Purpose |
| --- | --- |
| `versions.tf` | Defines the supported Terraform and OCI provider versions. |
| `provider.tf` | Configures the OCI region and selected authentication method. |
| `variables.tf` | Declares input parameters, types, and validation rules. |
| `terraform.tfvars.example` | Provides the example lab settings; copy it to `terraform.tfvars`. |
| `terraform.tfvars` | Contains your local attendee settings; created in step 3 and kept out of Git. |
| `main.tf` | Creates the lab compartment. |
| `outputs.tf` | Reports the compartment OCID, name, and lifecycle state. |
| `.terraform.lock.hcl` | Records the selected provider version and checksums; created or reused by `terraform init` and committed after review. |

Keep normal lab changes in `terraform.tfvars`; use `variables.tf` to check accepted inputs. Provider version constraints stay in `versions.tf`.

### 2. Prepare the environment and authentication

Use **Terraform 1.5 or later, below 2.0**, as required by `versions.tf`. The OCI provider constraint for this lab is `>= 7.0.0, < 8.0.0`. Terraform installs the provider during initialization. The command examples use Bash, available in OCI Cloud Shell and common Linux/macOS terminals. On Windows, use a compatible shell or adapt the shell syntax.

Choose one of the following authentication methods. In this lab, `auth` is the input that sets the OCI provider's `auth` argument. Add the selected values to `terraform.tfvars` in step 3.

#### Local machine (`auth = "APIKey"`)

Install Terraform CLI and configure an OCI API-signing-key profile in `~/.oci/config`. The profile must contain `tenancy`, `user`, `fingerprint`, and `key_file`. Register the matching public key with your OCI user, and keep the private key outside the repository.

```hcl
auth                = "APIKey"
config_file_profile = "DEFAULT"
```

Replace `DEFAULT` with your profile name if needed.

#### OCI Cloud Shell (`auth = "InstancePrincipal"`)

Open Cloud Shell from your signed-in OCI Console session. Terraform CLI is already installed; check its version with `terraform version`. Use Cloud Shell's existing authentication environment. You do not need to create an API-signing-key profile in `~/.oci/config` for this method.

```hcl
auth                = "InstancePrincipal"
config_file_profile = "DEFAULT"
```

Keep `config_file_profile = "DEFAULT"` in the parameter file with the current repository code: `variables.tf` still requires this input, although the provider passes it as `null` and ignores it when `auth = "InstancePrincipal"`. This value does not require a local `DEFAULT` API-key profile in Cloud Shell. Do not omit it unless the variable declaration has also been made optional.

Keep Cloud Shell's preconfigured authentication environment intact. The selected method must have the IAM permissions listed in **Before you begin**. Set `home_region` to your tenancy's home region for this lab.

### 3. Configure the lab parameters

From the repository root, open this lab's Terraform directory and create your local parameter file:

```bash
cd Compartment/terraform
cp terraform.tfvars.example terraform.tfvars
```

If `terraform.tfvars` already exists, edit that file instead of overwriting it. Set the authentication values from step 2, then review the following lab inputs:

| Parameter | What to enter or check |
| --- | --- |
| `home_region` | Your tenancy's home region; use this field instead of `region` in this lab. |
| `parent_compartment_ocid` | Existing parent compartment OCID, or tenancy OCID for the root. |
| `compartment_name` | Unique attendee name, such as `OCITestDriveBudapest-p01`. |
| `compartment_description` | A short, nonblank description. |
| `freeform_tags` | Tag map, or `{}` for none. |
| `enable_compartment_delete` | Keep `true` for the disposable workshop compartment. |

With `enable_compartment_delete = true`, the provider rejects an existing-name collision and can delete the compartment during cleanup. With `false`, it can adopt a same-named compartment and change it; destroy then removes the resource from state without deleting the compartment. Keep `true` for this lab.

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

For a new deployment, expect **1 to add, 0 to change, 0 to destroy**: `oci_identity_compartment.lab`. Verify the parent, compartment name, description, and tags.

Review the complete plan before applying. Stop if it includes unexpected changes or deletions. If you edit parameters after saving the plan, create and review a new plan.

### 6. Apply the reviewed plan

```bash
terraform apply lab.tfplan
terraform output
```

Applying a saved plan executes its reviewed changes without a second approval prompt. Wait for completion and keep the Terraform state for later updates and cleanup. If an apply only partially succeeds, retain the state, resolve the error, and create a fresh plan.

### 7. Verify deployment

```bash
terraform output -raw compartment_ocid
```

1. Open **Identity & Security → Compartments** and locate the new compartment.
2. Confirm its parent, name, and **Active** state.
3. Record the OCID for all subsequent labs. Allow for propagation if selectors do not show it immediately.

**Success criteria:** One Active compartment exists under the intended parent, and its OCID is recorded.

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
| Invalid OCID validation error | Replace the placeholder with the assigned parent or tenancy OCID. |
| Not authorized / not found | Confirm the parent OCID, tenancy, home region, and required IAM access with the instructor. |
| Name collision | Pick a unique attendee name, or, for a resource you own and intend to manage, import it once with `terraform import oci_identity_compartment.lab YOUR_COMPARTMENT_OCID`, then review a fresh plan. Import does not reconcile configuration automatically. |
| New compartment missing from selectors | Wait briefly for propagation, then refresh and check permissions. |
| Destroy fails | Remove remaining resources, policies, and child compartments before retrying. |
| Cannot create resources inside the new compartment | Ask the instructor to verify resource permissions; this lab creates no IAM policies. |

## Optional cleanup

Keep the compartment until all other labs have been cleaned up. Use the same deployment option that created each resource.

### Option A - OCI Console

1. Remove resources from the later labs first, using their original deployment tool/state.
2. Check all regions used, child compartments, and policies attached to the compartment. The compartment must be empty.
3. Open **Identity & Security → Compartments**, select the lab compartment, and choose **Delete**.
4. Confirm deletion and wait for the operation to complete; deletion is asynchronous.

### Option B - Terraform

From `Compartment/terraform/`, use the original state and parameter file. Create a cleanup plan:

```bash
terraform plan -destroy -out=cleanup.tfplan
terraform show cleanup.tfplan
```

Confirm the plan targets only your empty lab compartment. With `enable_compartment_delete = true`, the provider attempts actual OCI deletion. Remove any remaining resources, attached policies, and child compartments first, including resources in other regions.

After reviewing the plan, apply it:

```bash
terraform apply cleanup.tfplan
```

Keep Terraform state until cleanup is confirmed. Delete shared network resources and the compartment only after all dependent labs are finished.

## Oracle documentation references

- [Creating a compartment](https://docs.oracle.com/en-us/iaas/Content/Identity/compartments/To_create_a_compartment.htm)
- [Deleting a compartment](https://docs.oracle.com/en-us/iaas/Content/Identity/compartments/To_delete_a_compartment.htm)
- [Compartment resource and import behavior](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/identity_compartment.html)
- [Configure the OCI provider](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/configuring.htm)
- [Targeting multiple regions and the IAM home region](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/targeting-multiple-regions.htm)
- [Delete a compartment](https://docs.oracle.com/en-us/iaas/Content/Identity/compartments/To_delete_a_compartment.htm)
- [Using OCI Cloud Shell](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/devcloudshellgettingstarted.htm)
- [OCI SDK and CLI configuration file](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
