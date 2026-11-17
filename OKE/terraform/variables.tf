# Participant values belong in terraform.tfvars; defaults are centralized there.
variable "region" { type = string }
variable "auth_method" {
  description = "Authentication through an external OCI API key or security token profile."
  type        = string
  default     = "InstancePrincipal"
  validation {
    condition     = contains(["APIKey", "InstancePrincipal"], var.auth_method)
    error_message = "auth must be APIKey or InstancePrincipal."
  }
}
variable "config_file_profile" { type = string }
variable "compartment_id" { type = string }
variable "network_compartment_id" { type = string }
variable "vcn_name" { type = string }
variable "api_subnet_name" { type = string }
variable "lb_subnet_name" { type = string }
variable "worker_subnet_name" { type = string }
variable "cluster_name" { type = string }
variable "cluster_type" {
  type = string
  validation {
    condition     = contains(["BASIC_CLUSTER", "ENHANCED_CLUSTER"], var.cluster_type)
    error_message = "Use BASIC_CLUSTER or ENHANCED_CLUSTER."
  }
}
variable "kubernetes_version" {
  type = string
  validation {
    condition     = can(regex("^v[0-9]+\\.[0-9]+(\\.[0-9]+)?$", var.kubernetes_version))
    error_message = "Use vMAJOR.MINOR or vMAJOR.MINOR.PATCH, as returned by OKE."
  }
}
variable "cni_type" {
  type = string
  validation {
    condition     = var.cni_type == "FLANNEL_OVERLAY"
    error_message = "This lab supports FLANNEL_OVERLAY. VCN-native networking requires additional pod subnet configuration."
  }
}
variable "api_public_ip_enabled" { type = bool }
variable "api_allowed_cidrs" {
  type = set(string)
  validation {
    condition     = length(var.api_allowed_cidrs) > 0 && alltrue([for c in var.api_allowed_cidrs : can(cidrnetmask(c)) && c != "0.0.0.0/0"])
    error_message = "Supply your IPv4 client egress CIDR(s), typically /32; unrestricted 0.0.0.0/0 is not permitted by this lab."
  }
}
variable "pods_cidr" { type = string }
variable "services_cidr" { type = string }
variable "node_pool_name" { type = string }
variable "availability_domain" { type = string }
variable "node_shape" { type = string }
variable "node_ocpus" {
  type = number
  validation {
    condition     = var.node_ocpus > 0
    error_message = "OCPUs must be positive; also check shape limits."
  }
}
variable "node_memory_gbs" {
  type = number
  validation {
    condition     = var.node_memory_gbs > 0
    error_message = "Memory must be positive; also check shape limits."
  }
}
variable "node_count" {
  type = number
  validation {
    condition     = var.node_count >= 1 && floor(var.node_count) == var.node_count
    error_message = "Node count must be a positive integer."
  }
}
variable "node_image_name_regex" {
  type = string
  validation {
    condition     = can(regexall(var.node_image_name_regex, ""))
    error_message = "Supply a valid regular expression."
  }
}
variable "node_image_id" {
  type        = string
  description = "Empty uses strict name discovery; otherwise an OKE-compatible regional image OCID from node-pool-options."
}
variable "disable_legacy_imds" { type = bool }
variable "freeform_tags" { type = map(string) }
