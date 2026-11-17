variable "region" {
  description = "OCI region identifier."
  type        = string
}

variable "auth_method" {
  description = "Authentication through an external OCI API key or security token profile."
  type        = string
  default     = "InstancePrincipal"
  validation {
    condition     = contains(["APIKey", "InstancePrincipal"], var.auth_method)
    error_message = "auth must be APIKey or InstancePrincipal."
  }
}

variable "config_file_profile" {
  description = "API-key profile in ~/.oci/config."
  type        = string
}

variable "compartment_ocid" {
  description = "Existing compartment for the database system."
  type        = string
}

variable "network_compartment_ocid" {
  description = "Existing VCN/subnet compartment; null uses compartment_ocid."
  type        = string
  nullable    = true
}

variable "db_system_name" {
  description = "Database system display name."
  type        = string
}

variable "db_version" {
  description = "PostgreSQL major version, as a string."
  type        = string
}

variable "node_count" {
  description = "Total nodes: one primary plus read replicas."
  type        = number
  validation {
    condition     = var.node_count >= 1 && floor(var.node_count) == var.node_count
    error_message = "node_count must be a positive integer."
  }
}

variable "storage_iops" {
  description = "Database optimized storage performance tier in IOPS."
  type        = number
  validation {
    condition     = contains([75000, 150000, 225000, 300000, 375000, 450000, 525000, 600000, 675000, 750000], var.storage_iops)
    error_message = "Select an OCI PostgreSQL performance tier from 75000 through 750000 in increments of 75000."
  }
}

variable "availability_domain" {
  description = "Tenancy-specific AD name, used for AD-local storage."
  type        = string
}

variable "is_regionally_durable" {
  description = "false uses AD-specific storage; true uses regional storage."
  type        = bool
}

variable "shape" {
  description = "Supported OCI PostgreSQL shape name."
  type        = string
}

variable "ocpu_count" {
  description = "OCPUs per database node."
  type        = number
}

variable "memory_size_in_gbs" {
  description = "Memory in GB per database node."
  type        = number
}

variable "vcn_name" {
  description = "Exact display name of the existing VCN."
  type        = string
}

variable "subnet_name" {
  description = "Exact display name of the existing private database subnet."
  type        = string
}

variable "primary_endpoint_private_ip" {
  description = "Unused private IPv4 address for the primary database endpoint."
  type        = string
}

variable "reader_endpoint_enabled" {
  description = "Enable the optional single reader endpoint."
  type        = bool
}

variable "nsg_name" {
  description = "Display name of the NSG created by this lab."
  type        = string
}

variable "client_cidr" {
  description = "IPv4 source CIDR permitted to connect to PostgreSQL."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.client_cidr))
    error_message = "client_cidr must be a valid IPv4 CIDR."
  }
}

variable "db_admin_username" {
  description = "Initial database administrator username."
  type        = string
}

variable "db_admin_password" {
  description = "Initial administrator password. Supply using TF_VAR_db_admin_password or an untracked tfvars file."
  type        = string
  sensitive   = true
  nullable    = false
}

variable "backup_start" {
  description = "Daily backup start time in UTC, for example 02:00."
  type        = string
}

variable "backup_retention_days" {
  description = "Automatic backup retention in days."
  type        = number
}

variable "freeform_tags" {
  description = "Free-form tags applied to resources created by the lab."
  type        = map(string)
}
