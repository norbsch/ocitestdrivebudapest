# Reuse the VCN, subnets, routes and security lists from the network lab.
# NSGs add rules; existing security lists may already allow broader access.
resource "oci_core_network_security_group" "api" {
  compartment_id = var.compartment_id
  vcn_id         = local.vcn_id
  display_name   = "${var.cluster_name}-api-nsg"
  freeform_tags  = var.freeform_tags
}
resource "oci_core_network_security_group" "worker" {
  compartment_id = var.compartment_id
  vcn_id         = local.vcn_id
  display_name   = "${var.cluster_name}-worker-nsg"
  freeform_tags  = var.freeform_tags
}

locals {
  # Worker self traffic includes Flannel VXLAN (UDP 8472) and inter-node pods.
  fixed_ingress = {
    api_workers_k8s = { target = "api", source = oci_core_network_security_group.worker.id, source_type = "NETWORK_SECURITY_GROUP", protocol = "6", port = 6443, icmp = false }
    api_workers_oke = { target = "api", source = oci_core_network_security_group.worker.id, source_type = "NETWORK_SECURITY_GROUP", protocol = "6", port = 12250, icmp = false }
    api_workers_mtu = { target = "api", source = local.subnets.worker.cidr_block, source_type = "CIDR_BLOCK", protocol = "1", port = null, icmp = true }
    workers_self    = { target = "worker", source = oci_core_network_security_group.worker.id, source_type = "NETWORK_SECURITY_GROUP", protocol = "all", port = null, icmp = false }
    workers_api     = { target = "worker", source = oci_core_network_security_group.api.id, source_type = "NETWORK_SECURITY_GROUP", protocol = "6", port = null, icmp = false }
    workers_mtu     = { target = "worker", source = local.subnets.api.cidr_block, source_type = "CIDR_BLOCK", protocol = "1", port = null, icmp = true }
  }
  client_ingress = { for c in var.api_allowed_cidrs : "client_${c}" => {
    target = "api", source = c, source_type = "CIDR_BLOCK", protocol = "6", port = 6443, icmp = false
  } }
  nsg_ids = { api = oci_core_network_security_group.api.id, worker = oci_core_network_security_group.worker.id }
}
resource "oci_core_network_security_group_security_rule" "ingress" {
  for_each                  = merge(local.fixed_ingress, local.client_ingress)
  network_security_group_id = local.nsg_ids[each.value.target]
  direction                 = "INGRESS"
  protocol                  = each.value.protocol
  source                    = each.value.source
  source_type               = each.value.source_type
  stateless                 = false
  description               = "OKE lab ${each.key}"
  dynamic "tcp_options" {
    for_each = each.value.port == null ? [] : [each.value.port]
    content {
      destination_port_range {
        min = tcp_options.value
        max = tcp_options.value
      }
    }
  }
  dynamic "icmp_options" {
    for_each = each.value.icmp ? [1] : []
    content {
      type = 3
      code = 4
    }
  }
}
resource "oci_core_network_security_group_security_rule" "egress" {
  for_each                  = local.nsg_ids
  network_security_group_id = each.value
  direction                 = "EGRESS"
  protocol                  = "all"
  destination               = "0.0.0.0/0"
  destination_type          = "CIDR_BLOCK"
  stateless                 = false
  description               = "Lab outbound traffic via existing gateways"
}
