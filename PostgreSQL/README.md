# Hands-on Lab: OCI Database with PostgreSQL

## Goal/Estimated Time for the Hands-on Lab

Create an OCI Database with PostgreSQL system in the existing lab network, using either the OCI Console or Terraform. Confirm its configuration and connect over TLS from a private lab VM.

**Estimated time:** 45–60 minutes, including provisioning. Provisioning time varies with regional capacity.

**Project:** OCITestDriveBudapest

Choose one deployment option for this lab. Using both with the same endpoint IP causes an address conflict. This lab creates billable database and storage resources; review the Console cost estimate before deployment.

## Contents

- [Goal/Estimated Time for the Hands-on Lab](#goalestimated-time-for-the-hands-on-lab)
- [Contents](#contents)
- [Before you begin](#before-you-begin)
- [Target configuration](#target-configuration)
- [Option A - Deployment steps for OCI Console](#option-a---deployment-steps-for-oci-console)
- [Option B - Deployment steps for Terraform](#option-b---deployment-steps-for-terraform)
- [Troubleshooting](#troubleshooting)
- [Optional cleanup](#optional-cleanup)
- [Oracle documentation references](#oracle-documentation-references)

## Before you begin

1. Complete the compartment and network labs. Have the target compartment OCID available.
2. Select **Germany Central (Frankfurt)** (`eu-frankfurt-1`). Confirm your tenancy's AD name. The prefix `sgUC` is tenancy-specific; another tenancy may use a different prefix.
3. Confirm the existing VCN is `p01-vcn`, with CIDR `10.0.0.0/16`, and the private database subnet is `p01-subnet-private-db`, with CIDR `10.0.2.0/24`. The subnet must have IPv6 disabled and enough unused addresses for the endpoints and database nodes. Verify `10.0.2.2` is unused.
4. Confirm sufficient PostgreSQL service limits and E5 capacity. The two nodes request a total of **4 OCPUs and 32 GB memory**, with **2 OCPUs and 16 GB per node**.
5. Have an existing VM in `10.0.1.0/24` and a working way to reach it, such as an OCI Bastion session or VPN. Its outbound network rules and host firewall must permit TCP 5432 to the database subnet. Install a compatible `psql` client on that VM. On Ubuntu, use `sudo apt update` followed by `sudo apt install -y postgresql-client`; package installation requires repository access.
6. Choose a database administrator username and a strong password accepted by the OCI creation form. The lab uses `labadmin`. Store the password for the connection test.

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

## Target configuration

All editable Terraform settings are collected in `terraform/terraform.tfvars.example`. Copy it to `terraform.tfvars` and edit that copy.

| Setting | Lab default | Terraform parameter |
| --- | --- | --- |
| Region | `eu-frankfurt-1` | `region` |
| Database system name | `p01-postgresql` | `db_system_name` |
| PostgreSQL major version | `17` | `db_version` |
| Database nodes | `2`: one primary and one read replica | `node_count` |
| Performance tier | 75K IOPS | `storage_iops = 75000` |
| Data placement | Availability Domain-specific | `is_regionally_durable = false` |
| Availability domain for storage | `sgUC:EU-FRANKFURT-1-AD-1` | `availability_domain` |
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
4. Enter `p01-postgresql` as the name and select PostgreSQL major version **17**.

### 3. Configure storage and hardware

1. Set **Node count** to **2** and **Performance tier** to **75,000 IOPS**.
2. Choose **Availability Domain-specific** placement and AD **sgUC:EU-FRANKFURT-1-AD-1**.
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

### 5. Verify and connect

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

   Expect PostgreSQL 17, the selected administrator, database `postgres`, and `pg_is_in_recovery()` returning `false` on the primary. `\conninfo` should report an SSL connection. The database administrator is a managed-service administrator, without PostgreSQL superuser access.

## Option B - Deployment steps for Terraform

### 1. Prepare the files and authentication

The lab includes one README for both deployment options:

| File | Purpose |
| --- | --- |
| `README.md` | Console and Terraform instructions |
| `terraform/versions.tf` | Terraform and OCI provider requirements |
| `terraform/.terraform.lock.hcl` | Provider selection and checksums from initialization |
| `terraform/provider.tf` | OCI region and authentication profile |
| `terraform/variables.tf` | Input definitions and validation |
| `terraform/terraform.tfvars.example` | Editable example parameters |
| `terraform/main.tf` | Existing network lookups, NSG, rule, and database system |
| `terraform/outputs.tf` | Database ID, endpoint details, CA certificate, and NSG ID |
| `terraform/.gitignore` | Excludes local parameters, state, plans, and downloaded providers |

Install Terraform 1.5 or later, below 2.0, and configure OCI API-key authentication in `~/.oci/config`. The profile must include your tenancy OCID, user OCID, API key fingerprint, and private-key file path. The example selects the `DEFAULT` profile. Authentication setup: [OCI SDK and CLI configuration](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm).

The provider constraint accepts OCI provider 8.29 or later within major version 8. The included `.terraform.lock.hcl` selects **8.29.0**. Retain and commit it to share that provider selection with attendees.

### 2. Customize parameters

From the extracted `postgresql-lab` folder:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

1. Replace `compartment_ocid` with the compartment created in the earlier lab.
2. If the VCN and subnet are in another compartment, set `network_compartment_ocid` to its OCID; otherwise keep `null`.
3. Check the profile, region, AD, network names, and endpoint IP. All requested defaults are already populated.
4. Change any lab settings in this parameter file. A different subnet requires a matching unused endpoint IP; a different client network requires an updated `client_cidr`. Names must identify exactly one VCN and one subnet in the selected compartment.

Supply the password through a Bash environment variable, avoiding shell history:

```bash
read -rsp 'Database administrator password: ' TF_VAR_db_admin_password
printf '\n'
export TF_VAR_db_admin_password
```

Alternatively, uncomment `db_admin_password` in your untracked `terraform.tfvars`, or let Terraform prompt. The sensitive flag redacts normal output, but the password is still stored in local Terraform state and saved plans. Keep these files private and out of Git.

### 3. Initialize and review

```bash
terraform init
terraform fmt -check
terraform validate
terraform plan -out=postgresql.tfplan
```

Expect **3 managed resources** to be added: the database system, an NSG, and its ingress rule. The existing VCN and subnet are read through data sources. Confirm no unrelated resources are changed.

The name lookups reject zero or multiple matches with a diagnostic, including a null-safe check for an empty OCI response. The configuration also checks that the subnet is private and has IPv6 disabled.

### 4. Deploy and inspect outputs

```bash
terraform apply postgresql.tfplan
terraform output db_system_ocid
terraform output db_system_state
terraform output primary_endpoint
terraform output -raw ca_certificate > dbsystem.pub
```

Wait for completion. Locate the system in the OCI Console and verify both nodes and all target settings. A Terraform operation does not create your client VM, Bastion connection, compartment, VCN, or subnet.

### 5. Test the connection

Transfer `dbsystem.pub` to the VM in the allowed client subnet. Follow **Option A, step 5**, using the FQDN and IP reported by `terraform output primary_endpoint`. If you changed the username or endpoint address, update the connection command accordingly.

After deployment, clear the temporary password variable and remove the saved plan when no longer needed:

```bash
unset TF_VAR_db_admin_password
rm -f postgresql.tfplan
```

## Troubleshooting

| Symptom | Check and resolution |
| --- | --- |
| No VCN or subnet match, or a null lookup response | Verify region, exact display names, network compartment, resource state, and IAM permissions. The compartment OCID must identify the compartment containing the network. |
| Multiple VCN or subnet matches | Use unique display names in the selected scope; update the parameter file after renaming in the owning lab. |
| Invalid availability domain | Check the tenancy-specific prefix and region; copy the full AD name from your tenancy. |
| Requested private IP unavailable | Check existing VNICs/endpoints and other attendees' resources. Choose another unused address within the database subnet. |
| IPv6 or private-subnet precondition fails | Select an IPv4-only private subnet, or correct the subnet configuration through the network lab. |
| Shape, version, or capacity error | Check regional PostgreSQL availability, supported shapes, PostgreSQL service limits, and capacity. Keep compatible OCPU/memory settings; tiers at or above 375K IOPS require at least 16 OCPUs. |
| `NotAuthorizedOrNotFound` | Check profile, resource OCIDs, compartment scope, PostgreSQL permissions, and network permissions in the network compartment. |
| Connection timeout | Confirm the VM has private connectivity, its egress permits TCP 5432, and the DB's attached NSG allows the actual client source. A standard Cloud Shell session or laptop has no automatic private path to this endpoint. |
| Certificate verification fails | Use the primary endpoint FQDN as `host`, the matching service CA certificate, and the correct file path. Keep `sslmode=verify-full`. |
| Authentication fails | Check the configured username and password. Use `postgres` as the initial connection database. |
| Terraform times out while creating | Inspect the OCI work request and resource before retrying. If OCI completed after the timeout but the resource is absent from state, import it using `terraform import oci_psql_db_system.lab <db-system-ocid>` before planning again. |
| A later plan proposes replacement | Review changes to version, endpoint, storage, and other creation-time attributes. Do not apply replacement to a database containing data you need. This example is intended for initial provisioning. |

## Optional cleanup

Export any data you need before deleting the lab database. Retained backups can continue to consume storage after system deletion.

**Console deployment:** Delete `p01-postgresql` from the DB Systems page and wait for deletion to finish. Review retained backups and remove only lab backups you no longer need. Then delete the ingress rule and `p01-postgresql-nsg`.

**Terraform deployment:** Run from the same Terraform directory, using the same parameter file and state. Supply `TF_VAR_db_admin_password` again, or enter the original value at the prompt, because it is a required input:

```bash
terraform plan -destroy -out=cleanup.tfplan
terraform apply cleanup.tfplan
rm -f cleanup.tfplan
unset TF_VAR_db_admin_password
```

Check retained backups separately in OCI. Terraform destroys its database system, NSG rule, and NSG; the earlier labs own the compartment and network. Keep Terraform state until cleanup is confirmed. Clean up the network and compartment only after all dependent labs are finished.

## Oracle documentation references

- [Creating a PostgreSQL database system](https://docs.oracle.com/en-us/iaas/Content/postgresql/create-db.htm)
- [PostgreSQL 17 support announcement](https://docs.oracle.com/en-us/iaas/releasenotes/postgresql/db-17.htm)
- [Supported PostgreSQL shapes](https://docs.oracle.com/en-us/iaas/Content/postgresql/supported-shapes.htm)
- [PostgreSQL performance tiers](https://docs.oracle.com/en-us/iaas/Content/postgresql/performance-tiers.htm)
- [Getting started and prerequisites](https://docs.oracle.com/en-us/iaas/Content/postgresql/getting-started.htm)
- [PostgreSQL IAM policies](https://docs.oracle.com/en-us/iaas/Content/postgresql/policies.htm)
- [Connecting to PostgreSQL](https://docs.oracle.com/en-us/iaas/Content/postgresql/connect-to-db.htm)
- [Terraform: PostgreSQL database system](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/r/psql_db_system.html)
- [Terraform: connection details](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/docs/d/psql_db_system_connection_detail.html)

Prepared against Oracle documentation checked on 16 November 2026. Console labels can vary as OCI evolves. The files require validation with your tenancy's permissions and capacity before attendee use.

**Package checks:** Terraform formatting, parameter coverage, and README section/link checks passed. Provider initialization succeeded with OCI provider 8.29.0. Full `terraform validate` was blocked by the authoring environment's restriction on provider-local Unix sockets. No live OCI plan, deployment, or database connection test was performed; run the validation and deployment steps above in your OCI-enabled environment.
