from .models import OrdenCompraStarsoft
from .forms import BaseDatosForm
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from rest_framework.decorators import api_view
import pandas as pd
import pytesseract
from PIL import Image
import pdfplumber



def extract_pdf_tables(file):
    with pdfplumber.open(file) as pdf:
        tables = []

        # Intentar extraer tablas de cada página del PDF
        for i, page in enumerate(pdf.pages):
            table = page.extract_table()

            if table:
                print(f"Tabla extraída en página {i + 1}:")
                headers = table[0]  # La primera fila contiene los encabezados
                table_data = [headers]  # Agregar los encabezados como la primera fila

                for row in table[1:]:
                    table_data.append(row)  # Agregar las filas de datos

                tables.append(table_data)
            else:
                print(f"No se encontró una tabla en la página {i + 1}")

        # Si no se extrajeron tablas, intentamos extraer texto y convertirlo
        if not tables:
            print("No se encontraron tablas, pero aquí está el texto extraído:")
            text = ""
            for page in pdf.pages:
                text += page.extract_text()  # Extraer todo el texto del PDF

            print(text)
            lines = text.splitlines()  # Dividir el texto en líneas

            data = []
            header_found = False

            # Encabezado ajustado según la estructura del texto
            header = ["No.","NRO CE", "FECHA", "PLACA", "TRANSPORTISTA", "BULTOS", "PESO BRUTO", "PESO NETO",
                      "Nros. Precintos SENASAG"]

            for line in lines:
                # Detectar si la línea es parte de la tabla (empieza con el encabezado)
                if line.startswith("No.") and not header_found:
                    header_found = True  # Marca que el encabezado ha sido encontrado
                elif header_found:
                    # Si encontramos la línea "TOTALES", detenemos la extracción sin agregar la línea
                    if "TOTALES" in line:
                        break
                    else:
                        # Separar las columnas por espacios
                        columns = line.split()

                        # Asegurarnos de tener al menos las 8 columnas esperadas antes de procesar
                        if len(columns) >= len(header):
                            # Organizar las columnas fijas
                            no = columns[0]  # No.
                            nro_ce = columns[1]  # NRO CE
                            fecha = columns[2]  # FECHA
                            placa = columns[3]  # PLACA

                            # Las últimas 4 columnas son siempre los mismos datos
                            bultos = columns[-4]
                            peso_bruto = columns[-3]
                            peso_neto = columns[-2]
                            nro_precintos = columns[-1]

                            # Todo lo que queda en el medio se considera como el nombre del transportista
                            transportista = " ".join(columns[4:-4])

                            # Crear la fila de datos organizada
                            row = [no, nro_ce, fecha, placa, transportista, bultos, peso_bruto, peso_neto,
                                   nro_precintos]
                            data.append(row)
            print("encontro encabezado?", header_found)
            # Crear un DataFrame con los datos extraídos
            df_text_table = pd.DataFrame(data, columns=header)
            # Convertir el DataFrame a una lista de diccionarios
            return df_text_table.to_dict(orient='records')

# Función para extraer datos de un archivo Excel
def extract_excel_data(file):
    try:
        df = pd.read_excel(file, sheet_name=None)
        data = {}
        for sheet_name, sheet_data in df.items():
            data[sheet_name] = sheet_data.to_dict(orient='records')  # Convertir a lista de diccionarios
        return data
    except Exception as e:
        return {"error": str(e)}

# Función para extraer texto de una imagen usando Tesseract
def extract_image_text(file):
    img = Image.open(file)
    text = pytesseract.image_to_string(img)
    return text

# Vista para subir y procesar archivo
@api_view(['POST'])
def upload_file(request):
    if 'file' in request.FILES:
        file = request.FILES['file']
        file_type = file.name.split('.')[-1].lower()

        try:
            if file_type == 'pdf':
                tables = extract_pdf_tables(file)
                response_data = {"tables": tables}
            elif file_type in ['xls', 'xlsx']:
                data = extract_excel_data(file)
                response_data = {"data": data}
            elif file_type in ['jpg', 'jpeg', 'png']:
                text = extract_image_text(file)
                response_data = {"text": text}
            else:
                response_data = {'message': 'Formato de archivo no soportado'}

            return JsonResponse({'status': 'success', 'data': response_data}, status=200)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({"error": "No se proporcionó archivo."}, status=400)




# Vista para listar las importaciones
def listar_importaciones(request):
    form = BaseDatosForm(request.POST or None)
    registros = None

    if request.method == 'POST' and form.is_valid():
        base_datos = form.cleaned_data['base_datos']
        registros = OrdenCompraStarsoft.objects.using(base_datos).all()  # Consultar en la base seleccionada

    return render(request, 'importaciones/lista_importaciones.html', {'form': form, 'registros': registros})


# Vista para buscar órdenes de importación
@csrf_exempt
def buscar_orden_importacion(request):
    if request.method == 'GET':
        base_datos = request.GET.get('base_datos')  # Base de datos seleccionada
        termino_busqueda = request.GET.get('query')  # Término de búsqueda

        # Valida que se haya proporcionado la base de datos y el término de búsqueda
        if base_datos and termino_busqueda:
            # Filtra los registros que coincidan con el término de búsqueda
            registros = OrdenCompraStarsoft.objects.using(base_datos).filter(
                CNUMERO__icontains=termino_busqueda
            ).values('CNUMERO', 'CDESARTIC', 'CCODARTIC', 'NCANTIDAD', 'CUNIDAD', 'NPREUNITA', 'NTOTVENT')[:5]

            # Serializa los resultados como JSON
            return JsonResponse(list(registros), safe=False, status=200)
        else:
            return JsonResponse({'error': 'Parámetros inválidos'}, status=400)

    return JsonResponse({'error': 'Método no permitido'}, status=405)



