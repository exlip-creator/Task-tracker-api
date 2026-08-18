provider "yandex" {
  service_account_key_file = var.service_account_key_file
  zone                     = var.zone
  folder_id                = var.folder_id
  cloud_id                 = var.cloud_id
}