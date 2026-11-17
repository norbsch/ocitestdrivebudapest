output "cluster_id" { value = oci_containerengine_cluster.lab.id }
output "node_pool_id" { value = oci_containerengine_node_pool.lab.id }
output "selected_worker_image" { value = try(local.image_candidates[0], null) }
output "api_endpoints" { value = oci_containerengine_cluster.lab.endpoints }
output "api_nsg_id" { value = oci_core_network_security_group.api.id }
output "worker_nsg_id" { value = oci_core_network_security_group.worker.id }
output "kubeconfig_command" {
  value = "oci ce cluster create-kubeconfig --cluster-id ${oci_containerengine_cluster.lab.id} --file ./kubeconfig-p01-oke --region ${var.region} --token-version 2.0.0 --kube-endpoint ${var.api_public_ip_enabled ? "PUBLIC_ENDPOINT" : "PRIVATE_ENDPOINT"} --profile ${var.config_file_profile}"
}
