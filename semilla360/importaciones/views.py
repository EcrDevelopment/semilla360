from .models import OrdenCompraStarsoft
from .forms import BaseDatosForm
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import pandas as pd
import os
from django.core.files.storage import FileSystemStorage
from rest_framework.decorators import api_view
import pdfplumber
import pytesseract
from PIL import Image
import pdfplumber
import pandas as pd
from tabula import read_pdf


def extract_pdf_tables(pdf_file):
    tables_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                tables_data.append(table)

                # Convertir las tablas a un formato de diccionario
    tables_dict = []
    for table in tables_data:
        # Usar la primera fila como los encabezados
        headers = table[0]
        for row in table[1:]:
            tables_dict.append(dict(zip(headers, row)))

    return tables_dict




# Función para extraer datos de un archivo Excel
def extract_excel_data(file):
    try:
        df = pd.read_excel(file, sheet_name=None)  # Cargar todas las hojas
        data = {}
        for sheet_name, sheet_data in df.items():
            data[sheet_name] = sheet_data.head()  # Muestra solo las primeras filas como vista previa
        return data
    except Exception as e:
        return {"error": str(e)}


# Función para extraer texto de una imagen usando Tesseract
def extract_image_text(file):
    img = Image.open(file)
    text = pytesseract.image_to_string(img)
    return text


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


@api_view(['POST'])
def upload_file(request):
    if request.FILES.get('file'):
        file = request.FILES['file']
        file_type = file.name.split('.')[-1].lower()
        fs = FileSystemStorage()

        file_path = fs.save(file.name, file)
        print(f"Archivo guardado en: {file_path}")
        print(f"Archivo cargado: {file.name} (Tipo: {file_type})")

        try:
            if file_type == 'pdf':
                print("Procesando archivo PDF para extraer tablas...")
                tables = extract_pdf_tables(file)
                response_data = {"tables": tables}
            elif file_type in ['xls', 'xlsx']:
                print("Procesando archivo Excel...")
                data = extract_excel_data(file)
                response_data = {"data": data}
            elif file_type in ['jpg', 'jpeg', 'png']:
                print("Procesando imagen para extraer texto...")
                text = extract_image_text(file)
                response_data = {"text": text}
            else:
                response_data = {'message': 'Formato de archivo no soportado'}
                print("Formato de archivo no soportado.")

            os.remove(file_path)
            print("Archivo eliminado después del procesamiento.")

            return JsonResponse({'status': 'success', 'data': response_data}, status=200)

        except Exception as e:
            #os.remove(file_path)
            print(f"Error en el procesamiento del archivo: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    print("No se proporcionó archivo.")
    return JsonResponse({"error": "No se proporcionó archivo."}, status=400)

