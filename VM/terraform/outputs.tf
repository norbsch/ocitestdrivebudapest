output "instances" {
  description = "Created instance IDs, ADs, private IPs, and lifecycle states."
  value = {
    for name, vm in oci_core_instance.vm : name => {
      id                  = vm.id
      availability_domain = vm.availability_domain
      private_ip          = vm.private_ip
      state               = vm.state
    }
  }
}

output "image_id" {
  description = "Region-specific OCID of the exact selected image."
  value       = one(data.oci_core_images.linux.images).id
}
