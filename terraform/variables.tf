variable "zone" {
  description = "Availability zone for the infrastructure"
  type        = string
  default     = "ru-central1-a"
}

variable "network_name" {
  description = "VPC network name"
  type        = string
  default     = "pet-project-network"
}

variable "subnet_name" {
  description = "Subnet name"
  type        = string
  default     = "pet-project-subnet"
}

variable "subnet_cidr" {
  description = "CIDR block for the subnet"
  type        = string
  default     = "10.10.0.0/24"
}

variable "vm_name" {
  description = "Name of the VM"
  type        = string
  default     = "pet-project-vm"
}

variable "vm_cores" {
  description = "Count of CPU cores for the VM"
  type        = number
  default     = 2
}

variable "vm_memory" {
  description = "Count of RAM for the VM in GB"
  type        = number
  default     = 2
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key for VM access"
  type        = string
}

variable "service_account_key_file" {
  description = "Path to the service account key file for Yandex Cloud"
  type        = string
}

variable "cloud_id" {
  description = "Cloud ID for Yandex Cloud"
  type        = string
}

variable "folder_id" {
  description = "Folder ID for Yandex Cloud"
  type        = string
}