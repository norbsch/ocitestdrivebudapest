# Select OSN services in the provider's region rather than hard-coding an OCID.
data "oci_core_services" "regional" {
  lifecycle {
    postcondition {
      condition = length([
        for s in self.services : s
        if can(regex(var.routing.service_name_pattern, s.name))
      ]) == 1
      error_message = "Expected exactly one regional OSN service. Check routing.service_name_pattern and the selected region."
    }
  }
}

locals {
  osn_service = one([
    for s in data.oci_core_services.regional.services : s
    if can(regex(var.routing.service_name_pattern, s.name))
  ])
}

resource "oci_core_vcn" "lab" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}-${var.vcn.name}"
  cidr_blocks    = [var.vcn.cidr_block]
  dns_label      = var.vcn.dns_label
  freeform_tags  = var.freeform_tags
}

resource "oci_core_internet_gateway" "lab" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.lab.id
  display_name   = "${var.name_prefix}-${var.gateways.internet_name}"
  enabled        = var.gateways.internet_enabled
  freeform_tags  = var.freeform_tags
}

resource "oci_core_nat_gateway" "lab" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.lab.id
  display_name   = "${var.name_prefix}-${var.gateways.nat_name}"
  block_traffic  = var.gateways.nat_blocked
  freeform_tags  = var.freeform_tags
}

resource "oci_core_service_gateway" "lab" {
  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.lab.id
  display_name   = "${var.name_prefix}-${var.gateways.service_name}"
  freeform_tags  = var.freeform_tags

  services {
    service_id = local.osn_service.id
  }
}

# Each subnet gets its own table. Only private tables receive the OSN route.
resource "oci_core_route_table" "subnet" {
  for_each = var.subnets

  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.lab.id
  display_name   = "${var.name_prefix}-${each.value.route_table_name}"
  freeform_tags  = var.freeform_tags

  route_rules {
    destination       = var.routing.default_destination
    destination_type  = "CIDR_BLOCK"
    network_entity_id = each.value.is_public ? oci_core_internet_gateway.lab.id : oci_core_nat_gateway.lab.id
  }

  dynamic "route_rules" {
    for_each = each.value.is_public ? [] : [local.osn_service]
    content {
      destination       = route_rules.value.cidr_block
      destination_type  = "SERVICE_CIDR_BLOCK"
      network_entity_id = oci_core_service_gateway.lab.id
    }
  }
}

resource "oci_core_security_list" "subnet" {
  for_each = var.subnets

  compartment_id = var.compartment_id
  vcn_id         = oci_core_vcn.lab.id
  display_name   = "${var.name_prefix}-${each.value.security_list_name}"
  freeform_tags  = var.freeform_tags

  # Internal ingress tracks VCN CIDR changes automatically.
  ingress_security_rules {
    source      = var.vcn.cidr_block
    source_type = "CIDR_BLOCK"
    protocol    = var.security.internal_protocol
    stateless   = var.security.stateless
  }

  # TCP protocol number 6 is fixed by the IP protocol specification.
  # No source_port_range means ALL source ports.
  dynamic "ingress_security_rules" {
    for_each = each.value.is_public ? var.security.public_ingress_tcp_ports : toset([])
    content {
      source      = var.security.public_ingress_source
      source_type = "CIDR_BLOCK"
      protocol    = "6"
      stateless   = var.security.stateless
      tcp_options {
        min = ingress_security_rules.value
        max = ingress_security_rules.value
      }
    }
  }

  egress_security_rules {
    destination      = var.security.egress_destination
    destination_type = "CIDR_BLOCK"
    protocol         = var.security.egress_protocol
    stateless        = var.security.stateless
  }
}

resource "oci_core_subnet" "lab" {
  for_each = var.subnets

  compartment_id             = var.compartment_id
  vcn_id                     = oci_core_vcn.lab.id
  display_name               = "${var.name_prefix}-${each.value.name}"
  cidr_block                 = each.value.cidr_block
  dns_label                  = each.value.dns_label
  prohibit_public_ip_on_vnic = !each.value.is_public
  route_table_id             = oci_core_route_table.subnet[each.key].id
  security_list_ids          = [oci_core_security_list.subnet[each.key].id]
  dhcp_options_id            = oci_core_vcn.lab.default_dhcp_options_id
  freeform_tags              = var.freeform_tags
  # Omitting availability_domain creates a regional subnet.
}
