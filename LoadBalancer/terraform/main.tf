locals {
  network_compartment_id = coalesce(var.network_compartment_id, var.compartment_id)
  backend_compartment_id = coalesce(var.backend_compartment_id, var.compartment_id)
}

data "oci_core_vcns" "lab" {
  compartment_id = local.network_compartment_id
  display_name   = var.network.vcn_name
  state          = "AVAILABLE"

  lifecycle {
    postcondition {
      condition     = length(coalesce(self.virtual_networks, [])) == 1
      error_message = "Expected exactly one AVAILABLE VCN with the configured name. Check region, network_compartment_id, permissions, and duplicate names."
    }
  }
}

data "oci_core_subnets" "lb" {
  compartment_id = local.network_compartment_id
  vcn_id         = data.oci_core_vcns.lab.virtual_networks[0].id
  display_name   = var.network.subnet_name
  state          = "AVAILABLE"

  lifecycle {
    postcondition {
      condition     = length(coalesce(self.subnets, [])) == 1
      error_message = "Expected exactly one AVAILABLE LB subnet with the configured name in the selected VCN and network compartment."
    }
  }
}

data "oci_core_instances" "backend" {
  for_each = var.backends

  compartment_id = local.backend_compartment_id
  display_name   = each.key
  state          = "RUNNING"

  lifecycle {
    postcondition {
      condition     = length(coalesce(self.instances, [])) == 1
      error_message = "Expected exactly one RUNNING VM named ${each.key}. Check region, backend_compartment_id, permissions, lifecycle state, and duplicate names."
    }
  }
}

data "oci_core_vnic_attachments" "backend" {
  for_each = var.backends

  compartment_id = local.backend_compartment_id
  instance_id    = data.oci_core_instances.backend[each.key].instances[0].id
}

locals {
  # Inspect all attached VNICs, rather than assuming the first returned VNIC is primary.
  attached_vnics = merge({}, [
    for name, result in data.oci_core_vnic_attachments.backend : {
      for attachment in coalesce(result.vnic_attachments, []) :
      "${name}/${attachment.vnic_id}" => {
        backend_name = name
        vnic_id      = attachment.vnic_id
      } if attachment.state == "ATTACHED"
    }
  ]...)
}

data "oci_core_vnic" "backend" {
  for_each = local.attached_vnics
  vnic_id  = each.value.vnic_id
}

locals {
  primary_vnics = {
    for name in keys(var.backends) : name => [
      for key, vnic in data.oci_core_vnic.backend : vnic
      if local.attached_vnics[key].backend_name == name && vnic.is_primary
    ]
  }
}

resource "oci_load_balancer_load_balancer" "lab" {
  compartment_id = var.compartment_id
  display_name   = var.load_balancer.name
  shape          = "flexible"
  is_private     = var.load_balancer.is_private
  ip_mode        = "IPV4"
  subnet_ids     = [data.oci_core_subnets.lb.subnets[0].id]

  shape_details {
    minimum_bandwidth_in_mbps = var.load_balancer.minimum_bandwidth_in_mbps
    maximum_bandwidth_in_mbps = var.load_balancer.maximum_bandwidth_in_mbps
  }

  # Omit reserved_ips for the default ephemeral public address.
  dynamic "reserved_ips" {
    for_each = var.load_balancer.reserved_public_ip_id == null ? [] : [var.load_balancer.reserved_public_ip_id]
    content {
      id = reserved_ips.value
    }
  }

  lifecycle {
    precondition {
      condition     = var.load_balancer.is_private || !data.oci_core_subnets.lb.subnets[0].prohibit_public_ip_on_vnic
      error_message = "A public load balancer requires a public subnet. Choose the public LB subnet."
    }
    precondition {
      condition     = var.load_balancer.is_private || contains([null, ""], data.oci_core_subnets.lb.subnets[0].availability_domain)
      error_message = "This single-subnet public LB lab requires a regional subnet. An AD-specific public LB needs a different two-subnet configuration."
    }
    precondition {
      condition     = alltrue([for vnics in values(local.primary_vnics) : length(vnics) == 1])
      error_message = "Each backend VM must have exactly one attached primary VNIC."
    }
  }
}

resource "oci_load_balancer_backend_set" "web" {
  load_balancer_id = oci_load_balancer_load_balancer.lab.id
  name             = var.backend_set.name
  policy           = var.backend_set.policy

  health_checker {
    protocol          = var.health_check.protocol
    port              = var.health_check.port
    url_path          = var.health_check.protocol == "HTTP" ? var.health_check.url_path : null
    return_code       = var.health_check.protocol == "HTTP" ? var.health_check.return_code : null
    interval_ms       = var.health_check.interval_ms
    timeout_in_millis = var.health_check.timeout_in_millis
    retries           = var.health_check.retries
  }
}

resource "oci_load_balancer_backend" "web" {
  for_each = var.backends

  load_balancer_id = oci_load_balancer_load_balancer.lab.id
  backendset_name  = oci_load_balancer_backend_set.web.name
  ip_address       = local.primary_vnics[each.key][0].private_ip_address
  port             = each.value.port
  weight           = each.value.weight
}

resource "oci_load_balancer_listener" "http" {
  load_balancer_id         = oci_load_balancer_load_balancer.lab.id
  default_backend_set_name = oci_load_balancer_backend_set.web.name
  name                     = var.listener.name
  protocol                 = var.listener.protocol
  port                     = var.listener.port

  connection_configuration {
    idle_timeout_in_seconds = var.listener.idle_timeout_in_seconds
  }
}

# Security lists, NSGs, route tables, VMs, and web servers are managed separately.
# Complete the manual networking steps in the shared README for either deployment option.
