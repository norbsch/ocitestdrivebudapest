locals {
  network_compartment_ocid = coalesce(var.network_compartment_ocid, var.compartment_ocid)
}

data "oci_core_vcns" "lab" {
  compartment_id = local.network_compartment_ocid
  display_name   = var.vcn_name
  state          = "AVAILABLE"

  lifecycle {
    postcondition {
      condition     = try(length(self.virtual_networks), 0) == 1
      error_message = "Expected exactly one AVAILABLE VCN matching vcn_name. Check region, compartment, display name, and IAM permissions."
    }
  }
}

data "oci_core_subnets" "lab" {
  compartment_id = local.network_compartment_ocid
  vcn_id         = one(data.oci_core_vcns.lab.virtual_networks).id
  display_name   = var.subnet_name
  state          = "AVAILABLE"

  lifecycle {
    postcondition {
      condition     = try(length(self.subnets), 0) == 1
      error_message = "Expected exactly one AVAILABLE subnet matching subnet_name in the selected VCN and network compartment."
    }
  }
}

locals {
  db_subnet = one(data.oci_core_subnets.lab.subnets)
}

resource "oci_core_network_security_group" "postgresql" {
  compartment_id = local.network_compartment_ocid
  vcn_id         = one(data.oci_core_vcns.lab.virtual_networks).id
  display_name   = var.nsg_name
  freeform_tags  = var.freeform_tags
}

resource "oci_core_network_security_group_security_rule" "postgresql_ingress" {
  network_security_group_id = oci_core_network_security_group.postgresql.id
  direction                 = "INGRESS"
  protocol                  = "6"
  source                    = var.client_cidr
  source_type               = "CIDR_BLOCK"
  stateless                 = false
  description               = "Allow PostgreSQL from the lab client subnet"

  tcp_options {
    destination_port_range {
      min = 5432
      max = 5432
    }
  }
}

resource "oci_psql_db_system" "lab" {
  compartment_id              = var.compartment_ocid
  display_name                = var.db_system_name
  db_version                  = var.db_version
  shape                       = var.shape
  instance_count              = var.node_count
  instance_ocpu_count         = var.ocpu_count
  instance_memory_size_in_gbs = var.memory_size_in_gbs
  system_type                 = "OCI_OPTIMIZED_STORAGE"
  freeform_tags               = var.freeform_tags

  network_details {
    subnet_id                      = local.db_subnet.id
    primary_db_endpoint_private_ip = var.primary_endpoint_private_ip
    is_reader_endpoint_enabled     = var.reader_endpoint_enabled
    nsg_ids                        = [oci_core_network_security_group.postgresql.id]
  }

  storage_details {
    system_type           = "OCI_OPTIMIZED_STORAGE"
    is_regionally_durable = var.is_regionally_durable
    availability_domain   = var.is_regionally_durable ? null : var.availability_domain
    iops                  = var.storage_iops
  }

  credentials {
    username = var.db_admin_username
    password_details {
      password_type = "PLAIN_TEXT"
      password      = var.db_admin_password
    }
  }

  management_policy {
    backup_policy {
      kind           = "DAILY"
      backup_start   = var.backup_start
      retention_days = var.backup_retention_days
    }
  }

  lifecycle {
    precondition {
      condition     = local.db_subnet.prohibit_public_ip_on_vnic
      error_message = "Select a private database subnet with public IP assignment prohibited."
    }
    precondition {
      condition     = try(length(local.db_subnet.ipv6cidr_blocks), 0) == 0 && try(length(local.db_subnet.ipv6cidr_block), 0) == 0
      error_message = "OCI PostgreSQL requires a subnet without IPv6 enabled."
    }
    precondition {
      condition     = var.storage_iops < 375000 || var.ocpu_count >= 16
      error_message = "Performance tiers of 375000 IOPS or higher require at least 16 OCPUs per node."
    }
  }

  timeouts {
    create = "120m"
    update = "120m"
    delete = "120m"
  }

  depends_on = [oci_core_network_security_group_security_rule.postgresql_ingress]
}

data "oci_psql_db_system_connection_detail" "lab" {
  db_system_id = oci_psql_db_system.lab.id
}
