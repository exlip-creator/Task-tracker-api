output "server_name" {
  description = "The name of the server"
  value       = yandex_compute_instance.server.name
}

output "server_private_ip" {
  description = "The private IP address of the server"
  value       = yandex_compute_instance.server.network_interface[0].ip_address
}

output "server_public_ip" {
  description = "The public IP address of the server"
  value       = yandex_compute_instance.server.network_interface[0].nat_ip_address
}