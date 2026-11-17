# PostgreSQL Hands-on Lab

**Project:** OCITestDriveBudapest

## Goal / Estimated time

Create an OCI Database with PostgreSQL system in the existing lab network, using either the OCI Console or Terraform. Confirm its configuration and connect over TLS from a private lab VM.

**Estimated time:** 45–60 minutes, including provisioning. Provisioning time varies with regional capacity.

This lab creates billable database and storage resources; review the cost estimate before deployment.

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

1. Complete the compartment and network labs. Have the target compartment OCID available.
2. Select **Germany Central (Frankfurt)** (`eu-frankfurt-1`). Confirm your tenancy's AD name. The prefix `GsUS` in the example is tenancy-specific; another tenancy may use a different prefix.
3. Confirm the existing VCN is `p01-vcn`, with CIDR `10.0.0.0/16`, and the private database subnet is `p01-subnet-private-db`, with CIDR `10.0.2.0/24`. The subnet must have IPv6 disabled and enough unused addresses for the endpoints and database nodes. Verify `10.0.2.2` is unused.
4. Have an existing VM in `10.0.1.0/24` and a working way to reach it, such as an OCI Bastion session or VPN. Its outbound network rules and host firewall must permit TCP 5432 to the database subnet. Install a compatible `psql` client on that VM. On Ubuntu, use `sudo apt update` followed by `sudo apt install -y postgresql-client`; package installation requires repository access.
5. Choose a database administrator username and a strong password accepted by the OCI creation form. The lab uses `labadmin`. Store the password for the connection test.

### 2. Confirm permissions and capacity

Confirm PostgreSQL service limits and E5 capacity for two nodes: **4 OCPUs and 32 GB RAM total**, with **2 OCPUs and 16 GB per node**. Review the database and storage cost estimate before deployment.

Have a tenancy administrator grant the required permissions before the lab. The following compartment-scoped example is for a training group; replace the names and identity-domain qualifier as appropriate:

```text
Allow group <domain>/<lab-group> to read compartments in tenancy
Allow group <domain>/<lab-group> to manage postgres-db-systems in compartment <lab-compartment>
Allow group <domain>/<lab-group> to manage postgres-backups in compartment <lab-compartment>
Allow group <domain>/<lab-group> to read postgres-configurations in compartment <lab-compartment>
Allow group <domain>/<lab-group> to read postgres-work-requests in compartment <lab-compartment>
Allow group <domain>/<lab-group> to manage virtual-network-family in compartment <network-compartment>
```

The database and network compartments can be the same. If using OCI Vault instead of entering a password, additional permissions are needed; see the policy reference below. This Terraform example uses a supplied password and reuses the service's default database configuration.

### 3. Choose a deployment option

Choose **Option A - OCI Console** or **Option B - Terraform**. Both options create the target configuration below. Use one option for each lab deployment; do not create the same resources with both options.

Use your assigned attendee prefix in place of `p01`, consistently across all labs. Follow the workshop order: **Compartment → Network → VM → Load Balancer → PostgreSQL → OKE**.

For Option B, follow the two authentication methods in [Prepare the environment and authentication](#2-prepare-the-environment-and-authentication). Keep attendee settings in `terraform.tfvars` and use a separate Terraform directory and state for each lab and attendee.

## Target configuration

### Resource settings

| Setting | Lab default | Terraform parameter |
| --- | --- | --- |
| Region | `eu-frankfurt-1` | `region` |
| Database system name | `p01-postgresql` | `db_system_name` |
| PostgreSQL major version | `16` | `db_version` |
| Database nodes | `2`: one primary and one read replica | `node_count` |
| Performance tier | 75K IOPS | `storage_iops = 75000` |
| Data placement | Availability Domain-specific | `is_regionally_durable = false` |
| Availability domain for storage | `GsUS:EU-FRANKFURT-1-AD-1` | `availability_domain` |
| Shape | `PostgreSQL.VM.Standard.E5.Flex` | `shape` |
| OCPUs per node | `2` | `ocpu_count` |
| Memory per node | `16 GB` | `memory_size_in_gbs` |
| Existing VCN | `p01-vcn` | `vcn_name` |
| Existing private subnet | `p01-subnet-private-db` | `subnet_name` |
| Primary endpoint private IP | `10.0.2.2` | `primary_endpoint_private_ip` |
| Optional reader endpoint | Disabled | `reader_endpoint_enabled` |
| Database NSG | `p01-postgresql-nsg` | `nsg_name` |
| Allowed client source | `10.0.1.0/24`, TCP 5432 | `client_cidr` |
| Administrator | `labadmin` | `db_admin_username` |
| Automatic backups | Daily at 02:00 UTC, retained 7 days | `backup_start`, `backup_retention_days` |

`10.0.2.2` is the stable **primary database endpoint** address. OCI chooses individual node addresses. Two nodes do not require two manually assigned addresses. The optional reader endpoint can remain disabled while a read replica exists.

The selected AD controls AD-local storage placement. For regional storage, set `is_regionally_durable = true`; Terraform then omits the storage AD. AD-local storage does not provide cross-AD storage durability.

## Option A - Deployment steps for OCI Console

### 1. Prepare database network access

1. Open **Networking → Virtual Cloud Networks** and select the network compartment.
2. Open `p01-vcn`, then **Network Security Groups**.
3. Create an NSG named `p01-postgresql-nsg` in the network compartment.
4. Add this ingress rule:

   | Field | Value |
   | --- | --- |
   | Stateless | No — use a stateful rule |
   | Source type | CIDR |
   | Source CIDR | `10.0.1.0/24` |
   | IP protocol | TCP |
   | Source port range | All |
   | Destination port range | `5432` |

5. Save the rule. Stateful tracking permits response traffic. Review the subnet's existing security lists as well: allow rules from security lists and NSGs are combined, so remove any unintended broad database access through the owning network lab if needed.

### 2. Start the database creation wizard

1. Open **Databases → PostgreSQL → DB Systems**.
2. Select the lab compartment, then **Create PostgreSQL Database system**.
3. Select **Create new Database system** and continue.
4. Enter `p01-postgresql` as the name and select PostgreSQL major version **16**.

### 3. Configure storage and hardware

1. Set **Node count** to **2** and **Performance tier** to **75,000 IOPS**.
2. Choose **Availability Domain-specific** placement and AD **GsUS:EU-FRANKFURT-1-AD-1**.
3. Under hardware, select **AMD**, choose the E5 flexible PostgreSQL shape, then set **2 OCPUs** and **16 GB memory** per node. The Console may display the shape as `VM.Standard.E5.Flex` within the PostgreSQL service.
4. Use the service's default compatible database configuration and extensions.

### 4. Configure networking and credentials

1. Select the network compartment, VCN **p01-vcn**, and subnet **p01-subnet-private-db**.
2. Enter **10.0.2.2** as the private IP address.
3. Leave the optional reader endpoint disabled for the default lab.
4. Enable the use of network security groups and select **p01-postgresql-nsg**.
5. Enter administrator username **labadmin** and choose **Input password**. Supply your chosen password. If the Console offers OCI Vault instead, use an existing approved secret and its version with the required permissions.
6. Continue to management policies. Enable daily automatic backups at **02:00 UTC** with **7 days** retention. Leave backup copies and point-in-time recovery disabled for this lab; use Oracle-managed maintenance scheduling.
7. Review the configuration and estimated cost, then create the system.

### 5. Verify deployment

1. Wait until the database system is **Active** and both database nodes are available. Inspect **Work requests** if provisioning fails.
2. Confirm the version, shape, per-node resources, storage tier, subnet, and endpoint IP match the target table.
3. In **Connection details**, copy the primary endpoint FQDN and download the CA certificate. Transfer the certificate to the client VM as `dbsystem.pub`.
4. On the VM, substitute the endpoint FQDN and connect. `hostaddr` supplies the private IP while `host` allows TLS hostname verification:

   ```bash
   psql -W "host=<primary-endpoint-fqdn> hostaddr=10.0.2.2 port=5432 dbname=postgres user=labadmin sslmode=verify-full sslrootcert=./dbsystem.pub"
   ```

5. Enter your password, then run:

   ```sql
   SELECT version();
   SELECT current_user, current_database();
   SELECT pg_is_in_recovery();
   \conninfo
   \q
   ```

   Expect PostgreSQL 16, the selected administrator, database `postgres`, and `pg_is_in_recovery()` returning `false` on the primary. `\conninfo` should report an SSL connection. The database administrator is a managed-service administrator, without PostgreSQL superuser access.

**Success criteria:** The database system is Active with two available nodes, and the TLS-verified primary connection returns the expected PostgreSQL version, administrator, and `pg_is_in_recovery() = false`.

## Option B - Deployment steps for Terraform

Complete **Before you begin** first. This lab has one README for both deployment options. Run all Terraform commands from `PostgreSQL/terraform/` in your repository checkout.

### 1. Review the Terraform files

All paths in this table are relative to `PostgreSQL/terraform/`.

| File | Purpose |
| --- | --- |
| `versions.tf` | Defines the supported Terraform and OCI provider versions. |
| `provider.tf` | Configures the OCI region and selected authentication method. |
| `variables.tf` | Declares input parameters, types, and validation rules. |
| `terraform.tfvars.example` | Provides the example lab settings; copy it to `terraform.tfvars`. |
| `terraform.tfvars` | Contains your local attendee settings; created in step 3 and kept out of Git. |
| `main.tf` | Looks up the existing network, then creates the database system, NSG, and ingress rule. |
| `outputs.tf` | Reports the database OCID/state, endpoints, CA certificate, and NSG OCID. |
| `.terraform.lock.hcl` | Records the selected provider version and checksums; created or reused by `terraform init` and committed after review. |

Keep normal lab changes in `terraform.tfvars`; use `variables.tf` to check accepted inputs. Provider version constraints stay in `versions.tf`.

### 2. Prepare the environment and authentication

Use **Terraform 1.5 or later, below 2.0**, as required by `versions.tf`. The OCI provider constraint for this lab is `>= 8.29.0, < 9.0.0`. Terraform installs the provider during initialization. The command examples use Bash, available in OCI Cloud Shell and common Linux/macOS terminals. On Windows, use a compatible shell or adapt the shell syntax.

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
cd PostgreSQL/terraform
cp terraform.tfvars.example terraform.tfvars
```

If `terraform.tfvars` already exists, edit that file instead of overwriting it. Set the authentication values from step 2, then review the following lab inputs:

| Parameter | What to enter or check |
| --- | --- |
| `region`, `compartment_ocid` | Existing network region and target database compartment OCID. |
| `network_compartment_ocid` | Network compartment OCID, or `null` to reuse `compartment_ocid`. |
| `db_system_name`, `db_version`, `node_count` | `p01-postgresql`, version `16`, and two nodes, matching the current example. |
| `storage_iops`, `is_regionally_durable`, `availability_domain` | 75,000 IOPS, AD-local storage, and your tenancy's AD1 name. |
| `shape`, `ocpu_count`, `memory_size_in_gbs` | PostgreSQL E5 flexible shape, 2 OCPUs, and 16 GB per node. |
| `vcn_name`, `subnet_name`, `primary_endpoint_private_ip` | Existing network names and unused endpoint `10.0.2.2`. |
| `reader_endpoint_enabled` | Keep `false` for the default lab. |
| `nsg_name`, `client_cidr` | Database NSG name and allowed client CIDR `10.0.1.0/24`. |
| `db_admin_username` | `labadmin`, or your chosen database administrator. |
| `backup_start`, `backup_retention_days`, `freeform_tags` | Daily backup at `02:00` UTC, 7-day retention, and tags. |

Use your tenancy's full AD name; the example prefix `GsUS` is not portable. A different subnet needs a matching unused endpoint address. A different client network needs an updated `client_cidr`. Network names must uniquely identify the existing VCN and subnet.

#### Supply the database password

In Bash, enter the password without adding it to shell history:

```bash
read -rsp 'Database administrator password: ' TF_VAR_db_admin_password
printf '\n'
export TF_VAR_db_admin_password
```

Alternatively, let Terraform prompt for `db_admin_password`, or put it in your untracked local `terraform.tfvars`. The sensitive flag redacts normal output, but the password remains in Terraform state and saved plans. Keep those files private.

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

For a new deployment, expect **3 to add, 0 to change, 0 to destroy**: one database system, one NSG, and one ingress rule. Verify the version, two nodes, storage placement, OCPU/memory settings, subnet, endpoint IP, and allowed client CIDR. The existing VCN and subnet are read through data sources; no client VM or private access service is created.

Review the complete plan before applying. Stop if it includes unexpected changes or deletions. If you edit parameters after saving the plan, create and review a new plan.

### 6. Apply the reviewed plan

```bash
terraform apply lab.tfplan
terraform output
```

Applying a saved plan executes its reviewed changes without a second approval prompt. Wait for completion and keep the Terraform state for later updates and cleanup. If an apply only partially succeeds, retain the state, resolve the error, and create a fresh plan.

### 7. Verify deployment

```bash
terraform output db_system_ocid
terraform output db_system_state
terraform output primary_endpoint
terraform output -raw ca_certificate > dbsystem.pub
```

1. In the OCI Console, confirm the system is **Active**, both nodes are available, and all settings match the target table.
2. Transfer `dbsystem.pub` to the client VM in the allowed subnet.
3. Follow [Option A, step 5](#5-verify-deployment), substituting the output endpoint FQDN/IP and your configured username.
4. After verification, clear the temporary password variable and delete the saved plan when no longer needed:

   ```bash
   unset TF_VAR_db_admin_password
   rm -f lab.tfplan
   ```

**Success criteria:** The system is Active with two nodes, and a TLS-verified connection reaches the primary endpoint with the expected PostgreSQL version and administrator.

### 8. Update the configuration

Edit `terraform.tfvars` for routine changes, then repeat steps 4–7 with the same working directory and state. Generate a new plan each time. Avoid editing Terraform-managed resources directly in the Console, and never manage the same resource from two Terraform states.

Supply the password input again for later plans. Review replacement actions carefully before applying changes to version, endpoint, or storage settings.

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
| No VCN or subnet match, or a null lookup response | Verify region, exact display names, network compartment, resource state, and IAM permissions. The compartment OCID must identify the compartment containing the network. |
| Multiple VCN or subnet matches | Use unique display names in the selected scope; update the parameter file after renaming in the owning lab. |
| Invalid availability domain | Check the tenancy-specific prefix and region; copy the full AD name from your tenancy. |
| Requested private IP unavailable | Check existing VNICs/endpoints and other attendees' resources. Choose another unused address within the database subnet. |
| IPv6 or private-subnet precondition fails | Select an IPv4-only private subnet, or correct the subnet configuration through the network lab. |
| Shape, version, or capacity error | Check regional PostgreSQL availability, supported shapes, PostgreSQL service limits, and capacity. Keep compatible OCPU/memory settings; tiers at or above 375K IOPS require at least 16 OCPUs. |
| `NotAuthorizedOrNotFound` | Check the selected OCI identity, resource OCIDs, compartment scope, PostgreSQL permissions, and network permissions in the network compartment. |
| Connection timeout | Confirm the VM has private connectivity, its egress permits TCP 5432, and the DB's attached NSG allows the actual client source. A standard Cloud Shell session or laptop has no automatic private path to this endpoint. |
| Certificate verification fails | Use the primary endpoint FQDN as `host`, the matching service CA certificate, and the correct file path. Keep `sslmode=verify-full`. |
| Database login fails | Check the configured username and password. Use `postgres` as the initial connection database. |
| Terraform times out while creating | Inspect the OCI work request and resource before retrying. If OCI completed after the timeout but the resource is absent from state, import it using `terraform import oci_psql_db_system.lab <db-system-ocid>` before planning again. |
| A later plan proposes replacement | Review changes to version, endpoint, storage, and other creation-time attributes. Do not apply replacement to a database containing data you need. This example is intended for initial provisioning. |

## Optional cleanup

Export any data you need before deleting the database. Review retained backups separately. Use the same deployment option that created each resource.

### Option A - OCI Console

1. Export any database data you need before deletion.
2. Delete `p01-postgresql` from **PostgreSQL → DB Systems** and wait for completion.
3. Review retained backups and remove only lab backups you no longer need; they can continue to consume storage.
4. Delete the database ingress rule and `p01-postgresql-nsg` after the system releases them.

### Option B - Terraform

From `PostgreSQL/terraform/`, use the original state and parameter file. Create a cleanup plan:

Supply `TF_VAR_db_admin_password` again using the Bash prompt in Option B, step 3, or enter the original value when Terraform prompts; this remains a required input for a destroy plan.

```bash
terraform plan -destroy -out=cleanup.tfplan
terraform show cleanup.tfplan
```

Confirm the plan removes only the database system, NSG ingress rule, and NSG. Retained backups need separate review; the existing compartment and network belong to earlier labs.

After reviewing the plan, apply it:

```bash
terraform apply cleanup.tfplan
```

Clear the temporary password and delete plan files when no longer needed:

```bash
unset TF_VAR_db_admin_password
rm -f lab.tfplan cleanup.tfplan
```

Keep Terraform state until cleanup is confirmed. Delete shared network resources and the compartment only after all dependent labs are finished.

## Oracle documentation references

- [Creating a PostgreSQL database system](https://docs.oracle.com/en-us/iaas/Content/postgresql/create-db.htm)
- [Supported PostgreSQL shapes](https://docs.oracle.com/en-us/iaas/Content/postgresql/supported-shapes.htm)
- [PostgreSQL performance tiers](https://docs.oracle.com/en-us/iaas/Content/postgresql/performance-tiers.htm)
- [Getting started and prerequisites](https://docs.oracle.com/en-us/iaas/Content/postgresql/getting-started.htm)
- [PostgreSQL IAM policies](https://docs.oracle.com/en-us/iaas/Content/postgresql/policies.htm)
- [Connecting to PostgreSQL](https://docs.oracle.com/en-us/iaas/Content/postgresql/connect-to-db.htm)
- [Terraform: PostgreSQL database system](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/psql_db_system.html)
- [Terraform: connection details](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/d/psql_db_system_connection_detail.html)
- [OCI Terraform provider configuration and authentication](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/configuring.htm)
- [Using OCI Cloud Shell](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/devcloudshellgettingstarted.htm)
- [OCI SDK and CLI configuration file](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
