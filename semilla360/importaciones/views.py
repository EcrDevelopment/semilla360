import math
from datetime import datetime
from reportlab.lib.pagesizes import landscape, letter
from io import BytesIO
from reportlab.pdfgen import canvas
from .models import OrdenCompraStarsoft, Proveedor
from .forms import BaseDatosForm
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, FileResponse, HttpResponse
from rest_framework.decorators import api_view
import pandas as pd
import pytesseract
from PIL import Image
import pdfplumber
import json
from .utils import calcular_monto_descuento_estiba,renderizar_template,convertir_html_a_pdf,procesar_data_reporte
import os
import tempfile



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

            #print(text)
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
            #print("encontro encabezado?", header_found)
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

leyenda_codigos = {
    1: "Transbordo",
    2: "Pago estiba",
    3: "No pago estiba",
    4: "Pago parcial",
}

@api_view(['POST'])
def upload_file_excel(request):
    try:
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return JsonResponse({"error": "No se proporcionó archivo."}, status=400)

        # Leer el archivo Excel usando openpyxl
        df = pd.read_excel(uploaded_file, engine='openpyxl', skiprows=1, header=0)

        # Limpiar y renombrar columnas
        df.columns = ["Item", "PLACA", "sacos_cargados", "peso_cargado", "PLACA_Balanza",
                      "sacos_entregados", "peso_balanza", "Merma", "descuentos_faltantes",
                      "descuentos_rotos", "descuentos_humedos", "descuentos_mojados", "Status_pago"]

        # Renombrar columnas para el frontend
        df.rename(columns={
            "Item": "item_nombre",
            "PLACA": "placa_salida",
            "sacos_cargados": "sacos_cargados",
            "peso_cargado": "peso_salida",
            "PLACA_Balanza": "placa_llegada",
            "sacos_entregados": "sacos_descargados",
            "peso_balanza": "peso_llegada",
            "Merma": "merma",
            "descuentos_faltantes": "sacos_faltantes",
            "descuentos_rotos": "sacos_rotos",
            "descuentos_humedos": "sacos_humedos",
            "descuentos_mojados": "sacos_mojados",
            "Status_pago": "descripcion_pago"
        }, inplace=True)



        # Procesar códigos usando la leyenda
        def procesar_codigo(codigo):
            try:
                codigo_entero = int(math.floor(float(codigo)))
                return leyenda_codigos.get(codigo_entero, "Seleccione")
            except (ValueError, TypeError):
                return "Seleccione"

        # Aplicar procesamiento de códigos
        df["pago_estiba"] = df["descripcion_pago"].apply(procesar_codigo)

        # Borrar columnas que no necesito
        df.drop(columns=["item_nombre", "merma","descripcion_pago"], inplace=True)

        # Convertir el DataFrame en una respuesta JSON
        result = df.to_dict(orient='records')

        return JsonResponse({"data": result}, status=200)

    except Exception as e:
        return JsonResponse({"error": f"Error al procesar archivo: {str(e)}"}, status=400)

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
            # Filtra las órdenes que coincidan con el término de búsqueda
            registros = OrdenCompraStarsoft.objects.using(base_datos).filter(
                CNUMERO__icontains=termino_busqueda
            ).prefetch_related('detalles')[:5]  # Carga los detalles relacionados

            # Serializa las órdenes junto con sus detalles
            resultado = []
            for registro in registros:
                # Extraemos la orden principal
                orden = {
                    'CNUMERO': registro.CNUMERO,
                    'CDESARTIC': registro.CDESARTIC,
                    'CCODARTIC': registro.CCODARTIC,
                    'NCANTIDAD': registro.NCANTIDAD,
                    'CUNIDAD': registro.CUNIDAD,
                    'NPREUNITA': registro.NPREUNITA,
                    'NTOTVENT': registro.NTOTVENT,
                    'proveedor': registro.detalles.CDESPROVE,
                    'codprovee': registro.detalles.CCODPROVE,
                }

                #print(orden)
                resultado.append(orden)

            return JsonResponse(resultado, safe=False, status=200)
        else:
            return JsonResponse({'error': 'Parámetros inválidos'}, status=400)

    return JsonResponse({'error': 'Método no permitido'}, status=405)

@csrf_exempt
def buscar_proveedor(request):
    if request.method == 'GET':
        base_datos = request.GET.get('base_datos')  # Base de datos seleccionada
        termino_busqueda = request.GET.get('query')  # Término de búsqueda

        # Valida que se haya proporcionado la base de datos y el término de búsqueda
        if base_datos and termino_busqueda:
            # Filtra las órdenes que coincidan con el término de búsqueda
            registros = Proveedor.objects.using(base_datos).filter(
                PRVCNOMBRE__icontains=termino_busqueda
            )[:5]  # Carga los detalles relacionados

            # Serializa las órdenes junto con sus detalles
            resultado = []
            for registro in registros:
                # Extraemos la orden principal
                proveedor = {
                    'nombre': registro.PRVCNOMBRE,
                }

                #print(proveedor)
                resultado.append(proveedor)

            return JsonResponse(resultado, safe=False, status=200)
        else:
            return JsonResponse({'error': 'Parámetros inválidos'}, status=400)

    return JsonResponse({'error': 'Método no permitido'}, status=405)

@csrf_exempt
def generar_reporte(request):
    if request.method == 'POST':
        try:
            # Decodificar el cuerpo de la solicitud
            data = json.loads(request.body)

            # Obtener los datos principales
            dataForm = data.get('dataForm', {})
            dataTable = data.get('dataTable', [])
            dataExtra = data.get('dataExtraForm', {})

            # Variables
            suma_peso_salida_kg = 0.00
            suma_peso_llegada_kg = 0.00
            total_sacos_cargados=0
            total_sacos_descargados=0
            total_sacos_rotos = 0
            total_sacos_humedos = 0
            total_sacos_mojados = 0
            total_descuento_estiba=0.00
            merma_total=0.00
            pago_estiba_list = []
            empresa=''
            if dataForm["empresa"] == "bd_trading_starsoft":
                empresa="TRADING SEMILLA SAC"

            # Recorrer los datos de la tabla
            for item in dataTable:
                try:
                    suma_peso_salida_kg += float(str(item["pesoSalida"]).replace(",", ""))
                    suma_peso_llegada_kg += float(str(item["pesoLlegada"]).replace(",", ""))
                    total_sacos_cargados += int(str(item["sacosCargados"]))
                    total_sacos_descargados += int(str(item["sacosDescargados"]))
                except (ValueError, AttributeError) as e:
                    print(f"Error procesando item: {item}, error: {e}")
                total_sacos_rotos += int(item["sacosRotos"])  # Contar sacos rotos
                total_sacos_humedos += int(item["sacosHumedos"])  # Contar sacos húmedos
                total_sacos_mojados += int(item["sacosMojados"])  # Contar sacos mojado
                # Evaluar el valor de pagoEstiba
                # Evaluar el valor de pagoEstiba
                pago_estiba_value = item.get("pagoEstiba")

                if pago_estiba_value is None:
                    print(f"Advertencia: El campo 'pagoEstiba' está vacío para el item {item}")
                    continue

                # Caso 1: "No pago 100 bolivianos"
                if "No pago estiba" in pago_estiba_value:
                    # Concatenar placaLlegada y pagoEstiba
                    #formatted_value = f"{item['placaLlegada']} - {pago_estiba_value}"
                    # Agregar el resultado a la lista con un valor calculado
                    pago_estiba_list.append({
                        "placa":{item['placaLlegada']},
                        "detalle": pago_estiba_value,
                        "monto_descuento": calcular_monto_descuento_estiba(item["sacosDescargados"],
                                                                 dataExtra["tipoCambioDescExt"])
                    })

                # Caso 2: "Pago parcial"
                elif "Pago parcial" in pago_estiba_value:
                    pago_estiba_list.append({
                        "placa": {item['placaLlegada']},
                        "detalle": pago_estiba_value,
                        "monto_descuento": calcular_monto_descuento_estiba(item["sacosDescargados"],
                                                                           dataExtra["tipoCambioDescExt"])
                    })

            for item in pago_estiba_list:
                total_descuento_estiba+=item['monto_descuento']

            # Calcular la diferencia de peso (diferencia entre salida y llegada)
            diferencia_peso_kg = suma_peso_salida_kg - suma_peso_llegada_kg

            # Guardar la merma siempre
            merma_total = diferencia_peso_kg

            # Verificar si la diferencia de peso excede la merma permitida
            if diferencia_peso_kg > dataExtra["mermaPermitida"]:
                diferencia_peso_por_cobrar = diferencia_peso_kg - dataExtra["mermaPermitida"]
            else:
                diferencia_peso_por_cobrar = None  # Si no excede la merma permitida, no se cobra

            # Calcular los descuentos por sacos dañados
            descuento_sacos_rotos = total_sacos_rotos * dataExtra["precioSacosRotos"]
            descuento_sacos_humedos = total_sacos_humedos * dataExtra["precioSacosHumedos"]
            descuento_sacos_mojados = total_sacos_mojados * dataExtra["precioSacosMojados"]

            # Total de descuentos por sacos dañados
            total_descuentos_sacos = descuento_sacos_rotos + descuento_sacos_humedos + descuento_sacos_mojados

            # Precio base del flete (por tonelada)
            flete_base = dataForm["fletePactado"] * (suma_peso_salida_kg / 1000)  # Convertir kg a toneladas

            # Cálculo del pago final
            pago_final = flete_base - total_descuentos_sacos

            precio_por_tonelada = dataExtra["precioProd"] * 1000

            # Sumar flete pactado, margen financiero y gastos de nacionalización
            precio_bruto = precio_por_tonelada + dataForm["fletePactado"] + dataExtra["margenFinanciero"] + dataExtra[
                "gastosNacionalizacion"]

            # Calcular el IGV (18%) sobre el precio bruto
            igv = precio_bruto * 0.18

            # Calcular el precio final bruto sumando el IGV
            precio_bruto_final = precio_bruto + igv

            # Paso 2: Calcular el precio por kg
            precio_por_kg = precio_bruto_final / 1000

            # Paso 3: Calcular el descuento por diferencia de peso
            # Si la diferencia de peso por cobrar es positiva, calculamos el descuento
            if diferencia_peso_por_cobrar and diferencia_peso_por_cobrar > 0:
                descuento_por_diferencia_peso = diferencia_peso_por_cobrar * precio_por_kg
            else:
                descuento_por_diferencia_peso = 0  # No hay descuento si no hay diferencia de peso

            # Si hay diferencia de peso por cobrar, sumamos al pago final el monto correspondiente
            if diferencia_peso_por_cobrar and diferencia_peso_por_cobrar > 0:
                pago_final -= descuento_por_diferencia_peso

            # Si hay descuento por pago de estiba
            if total_descuento_estiba and total_descuento_estiba > 0:
                pago_final -= total_descuento_estiba

            ''' 
            print(f"----------------------FLETE CALCULADO-------------------")
            print(f"Flete base: ${flete_base:.2f}")
            print(f"Descuento por sacos rotos: {descuento_sacos_rotos}")
            print(f"Descuento por sacos húmedos: {descuento_sacos_humedos}")
            print(f"Descuento por sacos mojados: {descuento_sacos_mojados}")
            print(f"Total descuento por sacos dañados: ${total_descuentos_sacos}")
            print(f"Descuento por diferencia de peso: ${descuento_por_diferencia_peso:.2f}")
            print(f"Descuento de estibaje: ${total_descuento_estiba:.2f}")
            print(f"total a pagar: ${pago_final:.2f}")
            print(f"----------------------Final del reporte -------------------")
            '''

            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=landscape(letter))



            # Agregar contenido al PDF
            pdf.setFont("Helvetica", 10)
            pdf.drawString(40, 595, f"{empresa}")
            pdf.setFont("Helvetica", 11)
            pdf.drawString(250, 580, f"{dataForm['producto']}")
            pdf.setFont("Helvetica", 10)
            pdf.drawString(40, 560, f"Carta Porte: {dataForm['cartaPorte']}")
            pdf.setFont("Helvetica", 9)
            pdf.drawString(40, 540, f"N° de DUA: {dataForm['dua']}")
            pdf.drawString(150, 540,f"Fecha numeración: {datetime.strptime(dataForm['fechaNumeracion'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%d/%m/%Y')}")
            pdf.drawString(300, 540, f"Factura N°: {dataForm['numFactura']}")
            pdf.drawString(410, 540, f"O/C: {dataForm['oc']} ({dataForm['numRecojo']})")
            pdf.drawString(490, 540, f"Cant.: {total_sacos_cargados} sacos")
            pdf.drawString(590, 540, f"{suma_peso_salida_kg:.2f} Kg.")

            '''
            # Crear tabla con datos de la tabla
            data = [['Placa S.', 'Sacos C.', 'Peso S.','Placa L.','Sacos D.','Peso L.','Merma']]  # Encabezado
            for item in dataTable:
                data.append([item["placa"], item["sacosCargados"], item["pesoSalida"],item["placaLlegada"],item["sacosDescargados"],item["pesoLlegada"],item["merma"]])

            table = Table(data)
            table.setStyle(TableStyle([
                ('TEXTCOLOR', (0, 0), (-1, 0), (0, 0, 0)),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 0), (-1, 0), (0.8, 0.8, 0.8)),
                ('GRID', (0, 0), (-1, -1), 0.5, (0, 0, 0)),
            ]))
            table.wrapOn(pdf, 100, 100)
            table.drawOn(pdf, 40, 410)
            '''

            # Definir el tamaño de la tabla y las columnas
            x = 40  # Posición horizontal inicial
            y = 510  # Posición vertical inicial
            ancho_columna = 50  # Ancho de cada columna
            alto_fila = 20  # Altura de cada fila

            # Agregar encabezado con varias columnas combinadas
            pdf.setFont("Helvetica-Bold", 10)

            # Dibujar el encabezado combinado (4 columnas combinadas)
            pdf.setFillColorRGB(0.8, 0.8, 0.8)  # Color de fondo gris claro
            pdf.rect(x, y, ancho_columna * 4, alto_fila, fill=1)  # Rectángulo para las columnas combinadas
            pdf.setFillColorRGB(0, 0, 0)  # Color de texto negro
            pdf.drawString(x + 5, y + 5, "MERCADERIA CARGADA")  # Texto del encabezado combinado

            # Dibujar el encabezado combinado (4 columnas combinadas)
            pdf.setFillColorRGB(0.8, 0.8, 0.8)  # Color de fondo gris claro
            pdf.rect((ancho_columna * 4) + x, y, ancho_columna * 4, alto_fila, fill=1)  # Rectángulo para las columnas combinadas
            pdf.setFillColorRGB(0, 0, 0)  # Color de texto negro
            pdf.drawString((ancho_columna * 4) + x + 5, y + 5, "MERCADERIA DESCARGADA")  # Texto del encabezado combinado

            # Dibujar el encabezado combinado (4 columnas combinadas)
            pdf.setFillColorRGB(0.8, 0.8, 0.8)  # Color de fondo gris claro
            pdf.rect(((ancho_columna * 4) * 2) + x, y, ancho_columna * 4, alto_fila,
                     fill=1)  # Rectángulo para las columnas combinadas
            pdf.setFillColorRGB(0, 0, 0)  # Color de texto negro
            pdf.drawString(((ancho_columna * 4) * 2) + x + 5, y + 5,"DESCUENTOS")  # Texto del encabezado combinado

            # Dibujar el resto de la tabla (con celdas separadas)


            # Filas y celdas
            y -= alto_fila  # Moverse hacia abajo para la siguiente fila
            #creacion de los headers
            pdf.setFont("Helvetica-Bold", 8)
            headers = ['N°','Placa S.', 'Sacos C.', 'Peso S.','Placa L.','Sacos D.','Peso L.','Merma',
                       'S. Falt.','S. rotos','S. humed.','S. mojados']
            for i, header in enumerate(headers):
                pdf.rect(x + (i * ancho_columna), y, ancho_columna, alto_fila)  # Dibujar cada celda
                pdf.drawString(x + (i * ancho_columna) + 5, y + 5, header)  # Escribir el texto

            y -= alto_fila

            pdf.setFont("Helvetica", 8)
            for idx, row in enumerate(dataTable, start=1):  # `start=1` hace que el índice comience desde 1
                # Convertir valores del objeto a una lista en el orden correcto
                values = [
                    str(idx),  # Índice secuencial que comienza en 1
                    str(row["placa"]), str(row["sacosCargados"]), str(row["pesoSalida"]),
                    str(row["placaLlegada"]), str(row["sacosDescargados"]), str(row["pesoLlegada"]),
                    str(row["merma"]),str(row["sacosFaltantes"]),str(row["sacosRotos"]),
                    str(row["sacosHumedos"]),str(row["sacosMojados"])
                ]
                for i,value in enumerate(values):
                    pdf.rect(x + (i * ancho_columna), y, ancho_columna, alto_fila)
                    pdf.drawString(x + (i * ancho_columna) + 5, y + 5, value)

                y -= alto_fila



                    # Guardar el archivo PDF
            pdf.showPage()

            # Finalizar el PDF
            pdf.save()

            # Configurar el buffer para su lectura
            buffer.seek(0)

            # Crear la respuesta del PDF
            response = HttpResponse(buffer, content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="reporte.pdf"'
            return response
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Error al procesar JSON'}, status=400)
    else:
                return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@csrf_exempt
def generar_reporte_dos(request):
    if request.method == 'POST':
        try:
            # Datos para el reporte
            data = json.loads(request.body)

            data_procesada=procesar_data_reporte(data)
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'importaciones/reporteFletesExtranjeros.html')

            # Renderizar el HTML
            html_content = renderizar_template(template_path, data_procesada)

            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                # Llama a la función para convertir el HTML a PDF y guardarlo en el archivo temporal
                convertir_html_a_pdf(html_content, temp_pdf.name)

                # Abre el archivo temporal para enviarlo como respuesta HTTP
                temp_pdf.seek(0)  # Asegúrate de que el puntero esté al principio del archivo
                response = HttpResponse(temp_pdf.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'inline; filename="reporte.pdf"'

                # Después de enviar el archivo, el archivo temporal se elimina automáticamente cuando termine
                return response
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Error al procesar JSON'}, status=400)
    else:
            return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


