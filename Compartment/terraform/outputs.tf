output "compartment_ocid" {
  description = "New lab compartment OCID. Use this for resource placement in subsequent labs."
  value       = oci_identity_compartment.lab.id
}

output "compartment_name" {
  description = "Name of the lab compartment."
  value       = oci_identity_compartment.lab.name
}

output "compartment_state" {
  description = "Lifecycle state of the lab compartment."
  value       = oci_identity_compartment.lab.state
}
