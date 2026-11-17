variable "region" {
  description = "OCI region with AD1 and AD2 and the existing network."
  type        = string
}

variable "config_file_profile" {
  description = "API-key profile in ~/.oci/config; this is separate from the VM SSH key."
  type        = string
}

variable "tenancy_ocid" {
  description = "Tenancy OCID used to look up availability domains."
  type        = string
}

variable "compartment_ocid" {
  description = "Existing lab compartment for both instances."
  type        = string
}

variable "network_compartment_ocid" {
  description = "Compartment containing the existing VCN and subnet."
  type        = string
}

variable "vcn_name" {
  description = "Exact display name of the existing VCN."
  type        = string
}

variable "subnet_name" {
  description = "Exact display name of the existing regional private VM subnet."
  type        = string
}

variable "image_display_name" {
  description = "Exact platform image name, with no automatic fallback to latest."
  type        = string
}

variable "shape" {
  description = "Compute shape for both instances."
  type        = string
}

variable "ocpus" {
  description = "OCPUs per instance."
  type        = number
}

variable "memory_in_gbs" {
  description = "Memory in GB per instance."
  type        = number
}

variable "ssh_public_key_path" {
  description = "Local path to the one public key installed on both VMs."
  type        = string
}

variable "instances" {
  description = "Instance display names mapped to AD numbers and private IPv4 addresses."
  type = map(object({
    ad_number  = number
    private_ip = string
  }))
  validation {
    condition     = length(var.instances) == 3 && length(distinct([for vm in values(var.instances) : vm.private_ip])) == 3
    error_message = "Provide exactly three instances with distinct private IP addresses."
  }
  validation {
    condition     = alltrue([for vm in values(var.instances) : contains([1, 2, 3], vm.ad_number)])
    error_message = "Availability-domain numbers must be 1, 2, or 3."
  }
}
