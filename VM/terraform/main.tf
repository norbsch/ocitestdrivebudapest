data "oci_identity_availability_domain" "vm" {
  for_each       = var.instances
  compartment_id = var.tenancy_ocid
  ad_number      = each.value.ad_number
}

data "oci_core_vcns" "lab" {
  compartment_id = var.network_compartment_ocid
  display_name   = var.vcn_name
  state          = "AVAILABLE"
  lifecycle {
    postcondition {
      condition     = length(self.virtual_networks) == 1
      error_message = "Expected exactly one matching VCN in the network compartment. Check region, compartment, and name."
    }
  }
}

data "oci_core_subnets" "vm" {
  compartment_id = var.network_compartment_ocid
  vcn_id         = one(data.oci_core_vcns.lab.virtual_networks).id
  display_name   = var.subnet_name
  state          = "AVAILABLE"
  lifecycle {
    postcondition {
      condition     = length(self.subnets) == 1
      error_message = "Expected exactly one matching subnet in the selected VCN and network compartment."
    }
  }
}

data "oci_core_images" "linux" {
  compartment_id   = var.compartment_ocid
  shape            = var.shape
  state            = "AVAILABLE"

  filter {
    name   = "display_name"
    values = [var.image_display_name]
    regex  = false
  }
}

locals {
  subnet         = one(data.oci_core_subnets.vm.subnets)
  ssh_public_key = trimspace(file(pathexpand(var.ssh_public_key_path)))
}

resource "oci_core_instance" "vm" {
  for_each            = var.instances
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domain.vm[each.key].name
  display_name        = each.key
  shape               = var.shape

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_in_gbs
  }
  
  instance_options {
    are_legacy_imds_endpoints_disabled = true
  }
  create_vnic_details {
    subnet_id        = local.subnet.id
    private_ip       = each.value.private_ip
    assign_public_ip = false
  }

  source_details {
    source_type = "image"
    source_id   = one(data.oci_core_images.linux.images).id
  }

  metadata = {
    ssh_authorized_keys = local.ssh_public_key
  }

  lifecycle {
    precondition {
      condition     = local.subnet.availability_domain == null || local.subnet.availability_domain == ""
      error_message = "Use a regional subnet so both AD1 and AD2 can share it."
    }
    precondition {
      condition     = local.subnet.prohibit_public_ip_on_vnic
      error_message = "The selected subnet must be private (public IPs prohibited)."
    }
    precondition {
      condition = try(
        cidrhost("${each.value.private_ip}/${split("/", local.subnet.cidr_block)[1]}", 0) == cidrhost(local.subnet.cidr_block, 0) &&
        !contains([
          cidrhost(local.subnet.cidr_block, 0),
          cidrhost(local.subnet.cidr_block, 1),
          cidrhost(local.subnet.cidr_block, -1)
        ], each.value.private_ip), false
      )
      error_message = "Each private IPv4 address must belong to the subnet and must not be an OCI-reserved address."
    }
    precondition {
      condition     = can(regex("^(ssh-|ecdsa-)", local.ssh_public_key))
      error_message = "ssh_public_key_path must point to an OpenSSH public key, not a private key."
    }
  }
}
