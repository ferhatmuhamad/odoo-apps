# Odoo Apps — Ferhat Muhamad

Kumpulan module Odoo yang dipublikasikan di [Odoo Apps Store](https://apps.odoo.com).

## Versi yang didukung

| Branch | Odoo | Status |
|---|---|---|
| `19.0` | Odoo 19.0 | Aktif — branch pengembangan utama |
| `18.0` | Odoo 18.0 | Aktif |
| `17.0` | Odoo 17.0 | Aktif (EOL saat Odoo 20 rilis) |

Semua module dibangun **hanya di atas Odoo Community**, sehingga berjalan di
**Community maupun Enterprise**.

## Modules

<!-- Tambahkan tiap module baru ke tabel ini -->

| Module | Deskripsi | Versi | Lisensi |
|---|---|---|---|
| [`fm_quick_note`](fm_quick_note/) | Quick Notes — catatan pribadi dengan tag, prioritas, dan deadline | 17.0, 18.0, 19.0 | LGPL-3 |

## Instalasi

1. Clone repo ini ke `addons_path` instance Odoo kamu.
2. Restart Odoo dan Update Apps List.
3. Install module lewat menu **Apps**.

## Development

Environment lokal ada di `~/Documents/Projects/odoo-dev` (tidak ikut di repo ini).

```bash
DEV=~/Documents/Projects/odoo-dev

$DEV/run.sh 19                                  # http://localhost:8019
$DEV/run.sh 19 -d app19_dev -i nama_module      # install
$DEV/run.sh 19 -d app19_dev -u nama_module      # upgrade
```

## Lisensi

LGPL-3, kecuali disebutkan lain di `__manifest__.py` masing-masing module.

## Kontak

Ferhat Muhamad — ferhatmuhamad221@gmail.com
