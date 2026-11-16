# All attendee-specific values are supplied in terraform.tfvars.
variable "region" {
  description = "OCI region containing the existing network and backend VMs."
  type        = string
}

variable "config_file_profile" {
  description = "Profile in ~/.oci/config used for API-key authentication."
  type        = string
}

variable "compartment_id" {
  description = "OCID of the compartment where the load balancer is created."
  type        = string
}

variable "network_compartment_id" {
  description = "VCN/subnet compartment OCID; null uses compartment_id."
  type        = string
  nullable    = true
}

variable "backend_compartment_id" {
  description = "Backend VM compartment OCID; null uses compartment_id."
  type        = string
  nullable    = true
}

variable "network" {
  description = "Exact display names of the existing VCN and LB subnet."
  type = object({
    vcn_name    = string
    subnet_name = string
  })
}

variable "load_balancer" {
  description = "Flexible IPv4 LB settings. A null reserved_public_ip_id requests an ephemeral address for a public LB."
  type = object({
    name                      = string
    is_private                = bool
    reserved_public_ip_id     = optional(string)
    minimum_bandwidth_in_mbps = number
    maximum_bandwidth_in_mbps = number
  })

  validation {
    condition = (
      var.load_balancer.minimum_bandwidth_in_mbps >= 10 &&
      var.load_balancer.maximum_bandwidth_in_mbps <= 8000 &&
      var.load_balancer.minimum_bandwidth_in_mbps <= var.load_balancer.maximum_bandwidth_in_mbps &&
      floor(var.load_balancer.minimum_bandwidth_in_mbps) == var.load_balancer.minimum_bandwidth_in_mbps &&
      floor(var.load_balancer.maximum_bandwidth_in_mbps) == var.load_balancer.maximum_bandwidth_in_mbps
    )
    error_message = "Bandwidth must use whole Mbps values: 10 <= minimum <= maximum <= 8000."
  }

  validation {
    condition     = !var.load_balancer.is_private || var.load_balancer.reserved_public_ip_id == null
    error_message = "A private LB cannot use a reserved public IP. Set reserved_public_ip_id to null."
  }
}

variable "backend_set" {
  description = "Backend set name and OCI policy identifier."
  type = object({
    name   = string
    policy = string
  })

  validation {
    condition     = contains(["ROUND_ROBIN", "LEAST_CONNECTIONS", "IP_HASH"], var.backend_set.policy)
    error_message = "Policy must be ROUND_ROBIN, LEAST_CONNECTIONS, or IP_HASH."
  }
}

variable "backends" {
  description = "Map of existing VM display names to backend ports and weights; uses each VM's primary VNIC private IPv4 address."
  type = map(object({
    port   = number
    weight = number
  }))

  validation {
    condition = length(var.backends) > 0 && alltrue([
      for b in values(var.backends) :
      b.port >= 1 && b.port <= 65535 && floor(b.port) == b.port &&
      b.weight >= 1 && b.weight <= 100 && floor(b.weight) == b.weight
    ])
    error_message = "Specify at least one backend, with integer port 1-65535 and integer weight 1-100."
  }
}

variable "health_check" {
  description = "HTTP or TCP health check. HTTP settings are omitted from the resource for TCP."
  type = object({
    protocol          = string
    port              = number
    url_path          = string
    return_code       = number
    interval_ms       = number
    timeout_in_millis = number
    retries           = number
  })

  validation {
    condition = (
      contains(["HTTP", "TCP"], var.health_check.protocol) &&
      var.health_check.port >= 1 && var.health_check.port <= 65535 &&
      floor(var.health_check.port) == var.health_check.port &&
      startswith(var.health_check.url_path, "/") &&
      var.health_check.return_code >= 100 && var.health_check.return_code <= 599 &&
      floor(var.health_check.return_code) == var.health_check.return_code &&
      var.health_check.interval_ms > var.health_check.timeout_in_millis &&
      var.health_check.timeout_in_millis > 0 && var.health_check.retries >= 1 &&
      floor(var.health_check.retries) == var.health_check.retries
    )
    error_message = "Use HTTP or TCP, a valid integer port/status, a path starting with /, positive retries, and interval greater than timeout."
  }
}

variable "listener" {
  description = "Plain HTTP listener settings for this lab. HTTPS requires additional certificate configuration."
  type = object({
    name                    = string
    protocol                = string
    port                    = number
    idle_timeout_in_seconds = number
  })

  validation {
    condition = (
      var.listener.protocol == "HTTP" &&
      var.listener.port >= 1 && var.listener.port <= 65535 &&
      floor(var.listener.port) == var.listener.port &&
      var.listener.idle_timeout_in_seconds > 0
    )
    error_message = "This lab supports HTTP with an integer port 1-65535 and a positive idle timeout."
  }
}
