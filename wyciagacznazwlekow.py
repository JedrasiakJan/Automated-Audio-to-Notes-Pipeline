import csv

input_file = 'Rejestr_Produktow_Leczniczych_calosciowy_stan_na_dzien_20260407.csv'
output_file = 'leki_pro.csv'
leki = set()

# Próbujemy różne kodowania znaków
for enc in ['utf-8', 'cp1250', 'iso-8859-2']:
    try:
        with open(input_file, mode='r', encoding=enc) as f:
            reader = csv.reader(f, delimiter=';')
            for row in reader:
                if len(row) > 2:
                    # Dodajemy nazwę handlową (indeks 1) i substancję (indeks 2)
                    leki.add(row[1].strip().upper())
                    leki.add(row[2].strip().upper())
        break # Jeśli się udało, wychodzimy z pętli
    except (UnicodeDecodeError, IndexError):
        continue

# Zapisujemy wynik
with open(output_file, mode='w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['nazwa'])
    for lek in sorted(leki):
        if lek and lek != "NAZWA PRODUKTU": # Omijamy nagłówek
            writer.writerow([lek])

print(f"✅ Sukces! Wyciągnięto {len(leki)} nazw bez użycia Pandas.")