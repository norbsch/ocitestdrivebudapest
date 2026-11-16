output "load_balancer_id" {
  description = "Load balancer OCID."
  value       = oci_load_balancer_load_balancer.lab.id
}

output "load_balancer_ip_addresses" {
  description = "Assigned IPv4 addresses; public for the default configuration."
  value       = [for address in oci_load_balancer_load_balancer.lab.ip_address_details : address.ip_address]
}

output "listener_url" {
  description = "HTTP test URL; a private LB requires a client with VCN connectivity."
  value       = "http://${oci_load_balancer_load_balancer.lab.ip_address_details[0].ip_address}:${var.listener.port}/"
}

output "backend_endpoints" {
  description = "Resolved primary private IPs, ports, and weights for the backend VMs."
  value = {
    for name, backend in var.backends : name => {
      private_ip = local.primary_vnics[name][0].private_ip_address
      port       = backend.port
      weight     = backend.weight
    }
  }
}

output "lb_subnet_cidr" {
  description = "Use this source CIDR when manually permitting LB-to-backend traffic."
  value       = data.oci_core_subnets.lb.subnets[0].cidr_block
}
