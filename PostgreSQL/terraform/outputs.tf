output "db_system_ocid" {
  description = "OCID of the PostgreSQL database system."
  value       = oci_psql_db_system.lab.id
}

output "db_system_state" {
  description = "Database system lifecycle state."
  value       = oci_psql_db_system.lab.state
}

output "primary_endpoint" {
  description = "Primary endpoint FQDN, IP address, and port."
  value       = data.oci_psql_db_system_connection_detail.lab.primary_db_endpoint
}

output "reader_endpoint" {
  description = "Reader endpoint details when enabled."
  value       = data.oci_psql_db_system_connection_detail.lab.reader_endpoint
}

output "ca_certificate" {
  description = "Service CA certificate for TLS server verification."
  value       = data.oci_psql_db_system_connection_detail.lab.ca_certificate
}

output "nsg_ocid" {
  description = "OCID of the lab-created PostgreSQL NSG."
  value       = oci_core_network_security_group.postgresql.id
}
