# Declarations only: all attendee-editable values are in terraform.tfvars.
variable "region" {
  description = "OCI region identifier, for example eu-frankfurt-1."
  type        = string
}

variable "compartment_id" {
  description = "OCID of the existing training compartment."
  type        = string
  validation {
    condition     = startswith(var.compartment_id, "ocid1.") && !strcontains(var.compartment_id, "REPLACE_ME")
    error_message = "Replace REPLACE_ME with the existing training compartment OCID (or tenancy OCID for the root compartment)."
  }
}

variable "auth_method" {
  description = "Authentication through an external OCI API key or security token profile."
  type        = string
  default     = "InstancePrincipal"
  validation {
    condition     = contains(["APIKey", "InstancePrincipal"], var.auth)
    error_message = "auth must be APIKey or InstancePrincipal."
  }
}

variable "config_file_profile" {
  description = "Profile in ~/.oci/config; no private keys are stored in Terraform files."
  type        = string
}

variable "name_prefix" {
  description = "Participant identifier prepended to every display name."
  type        = string
  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9-]*$", var.name_prefix))
    error_message = "Use a participant identifier beginning with a letter, containing letters, digits, or hyphens."
  }
}

variable "vcn" {
  description = "VCN name suffix, IPv4 CIDR, and DNS label."
  type = object({
    name       = string
    cidr_block = string
    dns_label  = string
  })
  validation {
    condition     = can(cidrnetmask(var.vcn.cidr_block))
    error_message = "The VCN CIDR must be a valid IPv4 CIDR."
  }
  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9]{0,14}$", var.vcn.dns_label))
    error_message = "VCN DNS label must start with a letter and contain 1–15 alphanumeric characters."
  }
}

variable "gateways" {
  description = "Gateway name suffixes and traffic controls."
  type = object({
    internet_name    = string
    nat_name         = string
    service_name     = string
    internet_enabled = bool
    nat_blocked      = bool
    service_blocked  = bool
  })
}

variable "subnets" {
  description = "Regional subnet definitions; map keys are stable Terraform resource identities."
  type = map(object({
    name               = string
    cidr_block         = string
    dns_label          = string
    is_public          = bool
    route_table_name   = string
    security_list_name = string
  }))
  validation {
    condition     = length(var.subnets) > 0 && alltrue([for s in values(var.subnets) : can(cidrnetmask(s.cidr_block))])
    error_message = "Define at least one subnet and use valid IPv4 CIDRs."
  }
  validation {
    condition     = alltrue([for s in values(var.subnets) : can(regex("^[A-Za-z][A-Za-z0-9]{0,14}$", s.dns_label))])
    error_message = "Subnet DNS labels must start with a letter and contain 1–15 alphanumeric characters."
  }
}

variable "routing" {
  description = "Default route destination and case-insensitive regex selecting the regional OSN service."
  type = object({
    default_destination  = string
    service_name_pattern = string
  })
  validation {
    condition     = can(cidrnetmask(var.routing.default_destination))
    error_message = "Default route destination must be a valid IPv4 CIDR."
  }
}

variable "security" {
  description = "Shared security settings; internal ingress source is always derived from the VCN CIDR."
  type = object({
    stateless                = bool
    internal_protocol        = string
    egress_protocol          = string
    egress_destination       = string
    public_ingress_source    = string
    public_ingress_tcp_ports = set(number)
  })
  validation {
    condition = alltrue([
      for p in var.security.public_ingress_tcp_ports : p >= 1 && p <= 65535 && floor(p) == p
    ])
    error_message = "TCP destination ports must be integers between 1 and 65535."
  }
  validation {
    condition     = can(cidrnetmask(var.security.egress_destination)) && can(cidrnetmask(var.security.public_ingress_source))
    error_message = "Security rule source and destination must be valid IPv4 CIDRs."
  }
}

variable "freeform_tags" {
  description = "Freeform tags added to all created network resources."
  type        = map(string)
}
