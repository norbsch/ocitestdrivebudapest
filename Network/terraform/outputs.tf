output "vcn_id" {
  description = "Created VCN OCID."
  value       = oci_core_vcn.lab.id
}

output "subnets" {
  description = "Subnet OCIDs, addresses, access types, and security/routing assignments."
  value = {
    for key, subnet in oci_core_subnet.lab : key => {
      id               = subnet.id
      name             = subnet.display_name
      cidr_block       = subnet.cidr_block
      is_public        = !subnet.prohibit_public_ip_on_vnic
      route_table_id   = subnet.route_table_id
      security_list_id = one(subnet.security_list_ids)
    }
  }
}

output "gateways" {
  description = "Gateway OCIDs and selected regional OSN destination label."
  value = {
    internet_gateway_id = oci_core_internet_gateway.lab.id
    nat_gateway_id      = oci_core_nat_gateway.lab.id
    service_gateway_id  = oci_core_service_gateway.lab.id
    service_name        = local.osn_service.name
    service_cidr_label  = local.osn_service.cidr_block
  }
}
