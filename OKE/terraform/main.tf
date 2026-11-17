data "oci_core_vcns" "lab" {
  compartment_id = var.network_compartment_id
  display_name   = var.vcn_name
  state          = "AVAILABLE"
  lifecycle {
    postcondition {
      condition     = try(length(self.virtual_networks), 0) == 1
      error_message = "Expected exactly one available VCN. Check region, network compartment, name and permissions."
    }
  }
}

locals {
  vcn_id = try(data.oci_core_vcns.lab.virtual_networks[0].id, null)
  subnet_names = {
    api    = var.api_subnet_name
    lb     = var.lb_subnet_name
    worker = var.worker_subnet_name
  }
}

data "oci_core_subnets" "lab" {
  for_each       = local.subnet_names
  compartment_id = var.network_compartment_id
  vcn_id         = local.vcn_id
  display_name   = each.value
  state          = "AVAILABLE"
  lifecycle {
    postcondition {
      condition     = try(length(self.subnets), 0) == 1
      error_message = "Expected exactly one available subnet for ${each.key}: ${each.value}. Check compartment, VCN and name."
    }
  }
}

locals {
  subnets = { for k, v in data.oci_core_subnets.lab : k => try(v.subnets[0], null) }
}

data "oci_containerengine_cluster_option" "lab" {
  cluster_option_id              = "all"
  should_list_all_patch_versions = length(split(".", var.kubernetes_version)) == 3
}

data "oci_containerengine_node_pool_option" "lab" {
  node_pool_option_id            = "all"
  compartment_id                 = var.compartment_id
  node_pool_k8s_version          = var.kubernetes_version
  should_list_all_patch_versions = length(split(".", var.kubernetes_version)) == 3
}

locals {
  image_candidates = [
    for s in coalesce(data.oci_containerengine_node_pool_option.lab.sources, []) : s
    if s.source_type == "IMAGE" &&
    can(regex("-OKE-${replace(trimprefix(var.kubernetes_version, "v"), ".", "\\.")}([.-]|$)", s.source_name)) &&
    (var.node_image_id != "" ? s.image_id == var.node_image_id : can(regex(var.node_image_name_regex, s.source_name)))
  ]
  image_id = try(local.image_candidates[0].image_id, null)
}

resource "oci_containerengine_cluster" "lab" {
  compartment_id     = var.compartment_id
  name               = var.cluster_name
  type               = var.cluster_type
  kubernetes_version = var.kubernetes_version
  vcn_id             = local.vcn_id
  freeform_tags      = var.freeform_tags

  cluster_pod_network_options {
    cni_type = var.cni_type
  }
  endpoint_config {
    subnet_id            = local.subnets.api.id
    is_public_ip_enabled = var.api_public_ip_enabled
    nsg_ids              = [oci_core_network_security_group.api.id]
  }
  options {
    service_lb_subnet_ids = [local.subnets.lb.id]
    kubernetes_network_config {
      pods_cidr     = var.pods_cidr
      services_cidr = var.services_cidr
    }
  }
  lifecycle {
    precondition {
      condition     = contains(coalesce(data.oci_containerengine_cluster_option.lab.kubernetes_versions, []), var.kubernetes_version)
      error_message = "Requested Kubernetes version is not offered in this region. Run the README version discovery command and update terraform.tfvars."
    }
    precondition {
      condition     = !var.api_public_ip_enabled || !local.subnets.api.prohibit_public_ip_on_vnic
      error_message = "A public API endpoint requires a public subnet."
    }
    precondition {
      condition     = coalesce(local.subnets.api.availability_domain, "REGIONAL") == "REGIONAL" && coalesce(local.subnets.lb.availability_domain, "REGIONAL") == "REGIONAL"
      error_message = "Use regional subnets for the API endpoint and the single load balancer subnet."
    }
    precondition {
      condition     = length(local.image_candidates) == 1
      error_message = "Expected one compatible OKE worker image. Check version, build date, architecture and image OCID using node-pool-options. No fallback image is selected."
    }
  }
  depends_on = [oci_core_network_security_group_security_rule.ingress, oci_core_network_security_group_security_rule.egress]
}

resource "oci_containerengine_node_pool" "lab" {
  cluster_id         = oci_containerengine_cluster.lab.id
  compartment_id     = var.compartment_id
  name               = var.node_pool_name
  kubernetes_version = var.kubernetes_version
  node_shape         = var.node_shape
  freeform_tags      = var.freeform_tags
  node_metadata      = { areLegacyImdsEndpointsDisabled = tostring(var.disable_legacy_imds) }

  node_shape_config {
    ocpus         = var.node_ocpus
    memory_in_gbs = var.node_memory_gbs
  }
  node_source_details {
    source_type = "IMAGE"
    image_id    = local.image_id
  }
  node_config_details {
    size    = var.node_count
    nsg_ids = [oci_core_network_security_group.worker.id]
    placement_configs {
      availability_domain = var.availability_domain
      subnet_id           = local.subnets.worker.id
    }
    node_pool_pod_network_option_details {
      cni_type = var.cni_type
    }
  }
  lifecycle {
    precondition {
      condition     = local.subnets.worker.prohibit_public_ip_on_vnic
      error_message = "This lab expects a private worker subnet."
    }
    precondition {
      condition     = contains(coalesce(data.oci_containerengine_node_pool_option.lab.kubernetes_versions, []), var.kubernetes_version)
      error_message = "Requested worker Kubernetes version is unavailable."
    }
    precondition {
      condition     = contains(coalesce(data.oci_containerengine_node_pool_option.lab.shapes, []), var.node_shape)
      error_message = "Requested shape is not offered for OKE in this region."
    }
  }
}
