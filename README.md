<div align="center">
  <img src="https://raw.githubusercontent.com/Kyugito666/Kyugito666/main/assets/duong2.gif" alt="Logo" width="200">
  <h1 align="center">ProxySync</h1>
  <p align="center">
    Sebuah tool CLI canggih untuk memvalidasi, mengelola, dan mendistribusikan daftar proxy Anda ke berbagai direktori secara efisien.
  </p>
  
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python" alt="Python Version">
    <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
    <img src="https://img.shields.io/static/v1?label=PRs&message=welcome&color=brightgreen&style=for-the-badge" alt="PRs Welcome">
    <img src="https://img.shields.io/github/stars/Kyugito666/ProxySync?style=for-the-badge&logo=github&label=Stars" alt="GitHub Stars">
  </p>
</div>

---

## 🌟 Tampilan Antarmuka

ProxySync menggunakan antarmuka baris perintah (CLI) yang modern dan interaktif, membuatnya mudah dan menyenangkan untuk digunakan.

```text
   ┌───────────────────────────────────┐
   │             ProxySync             │
   │ Created by Kyugito666 & Gemini AI │
   └───────────────────────────────────┘

   ╭───────────── Main Menu ─────────────╮
   │ Option │ Description                │
   ├────────┼────────────────────────────┤
   │ [1]    │ Run Full Process           │
   │ [2]    │ Manage Target Paths        │
   │ [3]    │ Exit                       │
   ╰────────┴────────────────────────────╯
   Select an option (1, 2, 3) [3]: _
```

---

## ✨ Fitur Utama

-   **Antarmuka Profesional**: Dibangun dengan `rich` untuk pengalaman pengguna yang kaya dan responsif.
-   **Pengecekan Proxy Cepat**: Memanfaatkan *multi-threading* untuk memvalidasi daftar proxy dengan kecepatan tinggi.
-   **Anti-Duplikat Otomatis**: Secara cerdas mendeteksi dan menghapus proxy yang terduplikasi sebelum diproses.
-   **Manajemen Path Eksternal**: Kelola semua direktori target Anda dengan mudah melalui file `paths.txt` tanpa menyentuh kode.
-   **Distribusi Acak Independen**: Setiap direktori tujuan menerima daftar proxy dengan urutan yang diacak secara unik untuk menghindari pola.
-   **Backup & Logging**: Secara otomatis mem-backup file proxy asli Anda dan menyimpan daftar proxy yang gagal ke `fail_proxy.txt`.

---

## 🚀 Memulai

Ikuti langkah-langkah ini untuk menjalankan ProxySync di sistem Anda.

### 1. Prasyarat

-   [Python 3.8](https://www.python.org/downloads/) atau versi lebih baru.
-   [Git](https://git-scm.com/downloads/).

### 2. Instalasi

Proses instalasi dibagi per langkah agar mudah diikuti.

#### Untuk Windows
1.  **Clone Repositori**
    ```bash
    git clone [https://github.com/Kyugito666/ProxySync.git](https://github.com/Kyugito666/ProxySync.git)
    ```
2.  **Masuk ke Direktori Proyek**
    ```bash
    cd ProxySync
    ```
3.  **Buat Virtual Environment**
    ```bash
    python -m venv venv
    ```
4.  **Aktifkan Virtual Environment**
    ```bash
    .\venv\Scripts\activate
    ```
5.  **Instal Dependensi**
    ```bash
    pip install -r requirements.txt
    ```

#### Untuk Linux & macOS
1.  **Clone Repositori**
    ```bash
    git clone [https://github.com/Kyugito666/ProxySync.git](https://github.com/Kyugito666/ProxySync.git)
    ```
2.  **Masuk ke Direktori Proyek**
    ```bash
    cd ProxySync
    ```
3.  **Buat Virtual Environment**
    ```bash
    python3 -m venv venv
    ```
4.  **Aktifkan Virtual Environment**
    ```bash
    source venv/bin/activate
    ```
5.  **Instal Dependensi**
    ```bash
    pip install -r requirements.txt
    ```

---

## ⚙️ Cara Penggunaan

1.  **Isi Proxy**: Buka file `proxy.txt` dan masukkan daftar proxy Anda (satu per baris).
2.  **Tentukan Path**: Buka file `paths.txt` dan masukkan semua path direktori tujuan Anda (satu per baris).
3.  **Jalankan Script**: Pastikan *virtual environment* Anda aktif, lalu jalankan perintah:
    ```bash
    python run.py
    ```
4.  **Pilih Menu**:
    -   Pilih **Opsi 1** untuk menjalankan proses penuh.
    -   Pilih **Opsi 2** untuk mengelola direktori target.
    -   Pilih **Opsi 3** untuk keluar.

---

## 📁 Struktur Proyek

```
/ProxySync
├── run.py             # Skrip utama aplikasi
├── paths.txt          # Daftar direktori tujuan
├── proxy.txt          # Daftar proxy Anda
└── requirements.txt   # Daftar dependensi Python
```

---

## ✍️ Kreator

Proyek ini dibuat dan dikelola dengan ❤️ oleh:

| Avatar | Kontributor | Peran |
| :---: |:---:|:---:|
| <img src="https://avatars.githubusercontent.com/Kyugito666" width="50" style="border-radius:50%"> | **[Kyugito666](https://github.com/Kyugito666)** | Konsep & Pengembangan Utama |
| <img src="https://raw.githubusercontent.com/Kyugito666/Kyugito666/main/assets/gemini.png" width="50" style="border-radius:50%"> | **Gemini AI** | Asisten & Refactoring Kode |

Jangan ragu untuk mengunjungi profil saya dan melihat proyek-proyek lainnya!

[![Profil GitHub Kyugito666](https://img.shields.io/badge/GitHub-Kyugito666-black?style=for-the-badge&logo=github)](https://github.com/Kyugito666)

---

## 📄 Lisensi

Proyek ini dilisensikan di bawah Lisensi MIT.
