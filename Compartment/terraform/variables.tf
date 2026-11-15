variable "oci_config_profile" {
  description = "Existing API-key profile name in ~/.oci/config."
  type        = string

  validation {
    condition     = length(trimspace(var.oci_config_profile)) > 0
    error_message = "Set a nonempty OCI configuration profile name."
  }
}

variable "home_region" {
  description = "Tenancy home region identifier, such as eu-frankfurt-1; confirm with your instructor."
  type        = string

  validation {
    condition     = length(trimspace(var.home_region)) > 0
    error_message = "Set the tenancy home region identifier."
  }
}

variable "parent_compartment_ocid" {
  description = "OCID of the existing parent compartment, or tenancy OCID for the root."
  type        = string

  validation {
    condition     = can(regex("^ocid1\\.(tenancy|compartment)\\.", var.parent_compartment_ocid))
    error_message = "Use a tenancy OCID or an existing compartment OCID."
  }
}

variable "compartment_name" {
  description = "Unique attendee compartment name within the parent."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]{1,100}$", var.compartment_name))
    error_message = "Use 1-100 letters, numbers, periods, hyphens, or underscores."
  }
}

variable "compartment_description" {
  description = "Description of this training compartment."
  type        = string

  validation {
    condition     = length(trimspace(var.compartment_description)) >= 1 && length(var.compartment_description) <= 400
    error_message = "Use a nonblank description with at most 400 characters."
  }
}

variable "freeform_tags" {
  description = "Optional free-form tags; set to {} to omit them."
  type        = map(string)
}

variable "enable_compartment_delete" {
  description = "True: allow destroy and reject name collisions. False: destroy retains the compartment and name collisions may adopt an existing compartment."
  type        = bool
}
