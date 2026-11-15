# Only mocked providers are used. These tests do not call OCI or create resources.
mock_provider "oci" {
  mock_data "oci_core_services" {
    defaults = {
      services = [
        {
          id          = "ocid1.service.oc1..mockall"
          name        = "All FRA Services In Oracle Services Network"
          cidr_block  = "all-fra-services-in-oracle-services-network"
          description = "Mock regional OSN services"
        },
        {
          id          = "ocid1.service.oc1..mockobjectstorage"
          name        = "OCI FRA Object Storage"
          cidr_block  = "oci-fra-objectstorage"
          description = "Mock Object Storage only"
        }
      ]
    }
  }
  mock_resource "oci_core_internet_gateway" {
    defaults = { id = "ocid1.internetgateway.oc1..mock" }
  }
  mock_resource "oci_core_nat_gateway" {
    defaults = { id = "ocid1.natgateway.oc1..mock" }
  }
  mock_resource "oci_core_service_gateway" {
    defaults = { id = "ocid1.servicegateway.oc1..mock" }
  }
}

variables {
  compartment_id = "ocid1.compartment.oc1..mocktraining"
}

run "workshop_network" {
  command = apply

  assert {
    condition = (
      length(oci_core_subnet.lab) == 3 &&
      oci_core_subnet.lab["public_lb"].cidr_block == "10.0.0.0/24" &&
      !oci_core_subnet.lab["public_lb"].prohibit_public_ip_on_vnic &&
      oci_core_subnet.lab["private_vm"].cidr_block == "10.0.1.0/24" &&
      oci_core_subnet.lab["private_vm"].prohibit_public_ip_on_vnic &&
      oci_core_subnet.lab["private_db"].cidr_block == "10.0.2.0/24" &&
      oci_core_subnet.lab["private_db"].prohibit_public_ip_on_vnic
    )
    error_message = "The workshop requires one public and two private subnets with their specified CIDRs."
  }

  assert {
    condition = alltrue([
      for k, s in oci_core_subnet.lab :
      s.route_table_id == oci_core_route_table.subnet[k].id &&
      toset(s.security_list_ids) == toset([oci_core_security_list.subnet[k].id])
    ])
    error_message = "Each subnet must use its dedicated route table and only its dedicated security list."
  }

  assert {
    condition = (
      length(oci_core_route_table.subnet["public_lb"].route_rules) == 1 &&
      alltrue([for r in oci_core_route_table.subnet["public_lb"].route_rules :
        r.destination == "0.0.0.0/0" && r.network_entity_id == oci_core_internet_gateway.lab.id
      ]) &&
      alltrue([for k in ["private_vm", "private_db"] :
        length(oci_core_route_table.subnet[k].route_rules) == 2 &&
        anytrue([for r in oci_core_route_table.subnet[k].route_rules :
          r.destination == "0.0.0.0/0" && r.network_entity_id == oci_core_nat_gateway.lab.id
        ]) &&
        anytrue([for r in oci_core_route_table.subnet[k].route_rules :
          r.destination_type == "SERVICE_CIDR_BLOCK" &&
          r.destination == "all-fra-services-in-oracle-services-network" &&
          r.network_entity_id == oci_core_service_gateway.lab.id
        ])
      ])
    )
    error_message = "Public traffic must route to IGW; each private table must route internet to NAT and OSN to SGW."
  }

  assert {
    condition = alltrue([for sl in oci_core_security_list.subnet :
      alltrue([for r in sl.ingress_security_rules : !r.stateless]) &&
      length(sl.egress_security_rules) == 1 &&
      alltrue([for r in sl.egress_security_rules :
        !r.stateless && r.protocol == "all" && r.destination == "0.0.0.0/0"
      ]) &&
      anytrue([for r in sl.ingress_security_rules :
        r.source == "10.0.0.0/16" && r.protocol == "all"
      ])
    ])
    error_message = "All lists must allow VCN ingress and all egress, with every rule stateful."
  }

  assert {
    condition = (
      length(oci_core_security_list.subnet["public_lb"].ingress_security_rules) == 3 &&
      length(oci_core_security_list.subnet["private_vm"].ingress_security_rules) == 1 &&
      length(oci_core_security_list.subnet["private_db"].ingress_security_rules) == 1 &&
      toset(flatten([for r in oci_core_security_list.subnet["public_lb"].ingress_security_rules :
        [for p in r.tcp_options : p.min if p.min == p.max]
        if r.protocol == "6" && r.source == "0.0.0.0/0"
      ])) == toset([80, 443])
    )
    error_message = "Only the public subnet should have the two extra HTTP/HTTPS ingress rules."
  }
}

run "custom_vcn_and_web_port" {
  command = apply
  variables {
    vcn = {
      name       = "custom-vcn"
      cidr_block = "10.0.0.0/8"
      dns_label  = "customvcn"
    }
    security = {
      stateless                = false
      internal_protocol        = "all"
      egress_protocol          = "all"
      egress_destination       = "0.0.0.0/0"
      public_ingress_source    = "192.0.2.0/24"
      public_ingress_tcp_ports = [8080]
    }
  }
  assert {
    condition = alltrue([for sl in oci_core_security_list.subnet :
      anytrue([for r in sl.ingress_security_rules : r.source == "10.0.0.0/8" && r.protocol == "all"])
    ])
    error_message = "Internal ingress must follow a customized VCN CIDR."
  }
  assert {
    condition = (
      length(oci_core_security_list.subnet["public_lb"].ingress_security_rules) == 2 &&
      anytrue([for r in oci_core_security_list.subnet["public_lb"].ingress_security_rules :
        r.protocol == "6" && r.source == "192.0.2.0/24" &&
        anytrue([for p in r.tcp_options : p.min == 8080 && p.max == 8080])
      ])
    )
    error_message = "Public ingress must follow attendee-defined source and destination ports."
  }
}
