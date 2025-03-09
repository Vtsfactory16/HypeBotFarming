import pandas as pd
import os

# 📌 Ruta del archivo CSV (ajústala según tu necesidad)
input_file = "C:/Users/saxov/Downloads/btcusd_1-min_data.csv"
output_file = "C:/Users/saxov/Downloads/btcusd_1-min_data_clean.csv"

# Verificar si el archivo existe
if not os.path.exists(input_file):
    print(f"⚠️ Error: El archivo {input_file} no existe.")
    print("Por favor, verifica la ruta del archivo.")
    exit(1)

# 1️⃣ Cargar el dataset
print("Cargando el archivo CSV...")
df = pd.read_csv(input_file)

# 2️⃣ Revisar las primeras filas
print("\nPrimeras filas del archivo:")
print(df.head())

# 3️⃣ Convertir 'Timestamp' a formato de fecha legible
print("\nConvirtiendo Timestamp a formato Datetime...")
try:
    df['Timestamp'] = pd.to_datetime(df['Timestamp'], unit='s')
    df.rename(columns={'Timestamp': 'Datetime'}, inplace=True)
    df.set_index('Datetime', inplace=True)
    print("✅ Conversión exitosa.")
except Exception as e:
    print(f"⚠️ Error en la conversión: {e}")

# 4️⃣ Eliminar valores nulos (si existen)
missing_values = df.isnull().sum().sum()
if missing_values > 0:
    print(f"\n⚠️ Se encontraron {missing_values} valores nulos. Eliminando...")
    df.dropna(inplace=True)
    print("✅ Valores nulos eliminados.")
else:
    print("\n✅ No se encontraron valores nulos.")

# 5️⃣ Guardar los datos procesados en un nuevo archivo CSV
df.to_csv(output_file)
print(f"\n✅ Archivo limpio guardado como: {output_file}")

# 6️⃣ Mostrar información final del dataset
print("\nInformación del dataset procesado:")
print(df.info())
