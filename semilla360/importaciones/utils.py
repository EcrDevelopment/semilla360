from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa
import os


def renderizar_template(template_path, data):
    """
    Renderiza la plantilla HTML con datos dinámicos.
    """
    # Configura el entorno de Jinja2
    env = Environment(loader=FileSystemLoader(os.path.dirname(template_path)))
    template = env.get_template(os.path.basename(template_path))
    return template.render(data=data)

def convertir_html_a_pdf(html_content, output_path):
    """
    Convierte el contenido HTML en un archivo PDF.
    """
    with open(output_path, "wb") as output_file:
        pisa_status = pisa.CreatePDF(html_content, dest=output_file)
    return not pisa_status.err

def generar_pdf(template_path, output_path, data):
    """
    Genera un PDF a partir de una plantilla HTML y datos dinámicos.
    """
    # Renderiza el HTML con los datos
    html_content = renderizar_template(template_path, data)

    # Convierte el HTML a PDF
    exito = convertir_html_a_pdf(html_content, output_path)

    if exito:
        print(f"PDF generado exitosamente en: {output_path}")
    else:
        print("Hubo un error al generar el PDF.")

def calcular_monto_luego_dsctos_sacos(flete_base,total_descuento_sacos,total_descuento_por_dif_peso):
    result=flete_base-(total_descuento_sacos+total_descuento_por_dif_peso)
    print(flete_base,total_descuento_sacos,total_descuento_por_dif_peso)
    return round(result,2)

def calcular_descuento_sacos(total_sacos_faltantes,total_sacos_rotos,total_sacos_humedos,total_sacos_mojados):
    return total_sacos_faltantes+total_sacos_rotos+total_sacos_humedos+total_sacos_mojados

def calcular_monto_descuento_estiba(ref_base,cantidad, tipoCambio):
    """
    Calcula el monto de descuento para estiba basado en una regla de tres simple.

    Args:
        cantidad (int): La cantidad de sacos cargados.
        tipoCambio (float): El tipo de cambio para convertir el monto.

    Returns:
        float: El monto de descuento en la moneda correspondiente al tipo de cambio.
    """
    # Base para la regla de tres
    referencia_cantidad = ref_base
    referencia_descuento = 100  # Descuento en bolivianos para 560

    # Si la cantidad es exactamente igual a la referencia, usa directamente el valor
    if cantidad == referencia_cantidad:
        monto_descuento_moneda = (referencia_descuento / tipoCambio)/3
    else:
        # Aplicar regla de tres simple para otras cantidades
        total_descuento_bolivianos = (cantidad * referencia_descuento) / referencia_cantidad
        monto_descuento_moneda = (total_descuento_bolivianos / tipoCambio)/3

    return round(monto_descuento_moneda, 2)

def calcular_monto_descuento_sacos_faltantes(cantidad_sacos_faltantes,precio_sacos_faltantes):
    return round(cantidad_sacos_faltantes*precio_sacos_faltantes,2)

def calcular_peso_no_considerado_por_sacos_faltante(cantidad_sacos_faltantes, peso_por_saco=None):
    if peso_por_saco  and peso_por_saco > 0:
        return cantidad_sacos_faltantes * peso_por_saco
    else:
        return cantidad_sacos_faltantes * 50

def calcular_diferencia_de_peso_por_cobrar_kg(diferencia_de_peso, merma_permitida, peso_sacos_faltantes):
    # Verificar si la diferencia de peso excede la merma permitida
    if diferencia_de_peso > merma_permitida:
        # Calcular la diferencia por cobrar
        diferencia_por_cobrar = diferencia_de_peso - merma_permitida
        # Restar el peso de los sacos faltantes si aplica
        diferencia_por_cobrar -= peso_sacos_faltantes
        # Asegurarnos de no devolver valores negativos
        return max(diferencia_por_cobrar, 0)
    else:
        # Si no excede la merma permitida, no se cobra nada
        return 0

def calcular_costo_por_kg(flete_pactado,precio_producto,margen_financiero,gastos_nac):


    # Cálculo del precio por tonelada
    precio_por_tonelada = precio_producto * 1000



    # Sumar flete pactado, margen financiero y gastos de nacionalización
    precio_bruto = precio_por_tonelada + flete_pactado + margen_financiero + gastos_nac

    # Calcular el IGV (18%) sobre el precio bruto
    igv = precio_bruto * 0.18

    # Calcular el precio final bruto sumando el IGV
    precio_bruto_final = precio_bruto + igv

    # calcular precio por TM
    precio_por_tonelada_final = round(precio_bruto_final / 1.18, 2)

    # Paso 2: Calcular el precio por kg
    precio_por_kg = round(precio_bruto_final / 1000, 4)

    data={
        "precio_por_tonelada":precio_por_tonelada,
        "precio_bruto":precio_bruto,
        "igv":igv,
        "precio_bruto_final":precio_bruto_final,
        "precio_por_tonelada_final":precio_por_tonelada_final,
        "precio_por_kg":precio_por_kg,
    }
    return data

def procesar_data_reporte(data):
    # Obtener los datos principales
    dataForm = data.get('dataForm', {})
    dataTable = data.get('dataTable', [])
    dataExtra = data.get('dataExtraForm', {})

    # Variables
    suma_peso_salida_kg = 0.00
    suma_peso_llegada_kg = 0.00
    total_sacos_cargados = 0
    total_sacos_descargados = 0
    total_sacos_faltantes = 0
    total_sacos_rotos = 0
    total_sacos_humedos = 0
    total_sacos_mojados = 0
    total_descuento_estiba = 0.00
    total_descuento_sacos=0.00
    total_global_descuentos=0.00
    merma_total = 0.00
    pago_estiba_list = []
    empresa = ''

    fecha_numeracion=datetime.strptime(dataForm['fechaNumeracion'], '%Y-%m-%dT%H:%M:%S.%fZ').strftime('%d/%m/%Y')
    if dataForm["empresa"] == "bd_trading_starsoft":
        empresa = "TRADING SEMILLA SAC"
    elif dataForm["empresa"] == "bd_semilla_starsoft":
            empresa = "LA SEMILLA SEMILLA DE ORO SAC"
    elif dataForm["empresa"] == "bd_maximilian_starsoft":
            empresa = "MAXIMILIAN INVERSIONES SA"

    # Recorrer los datos de la tabla
    for item in dataTable:
        try:
            suma_peso_salida_kg += float(str(item["pesoSalida"]).replace(",", ""))
            suma_peso_llegada_kg += float(str(item["pesoLlegada"]).replace(",", ""))
            total_sacos_cargados += int(str(item["sacosCargados"]))
            total_sacos_descargados += int(str(item["sacosDescargados"]))
            merma_total += float(str(item["merma"]).replace(",", ""))
        except (ValueError, AttributeError) as e:
            print(f"Error procesando item: {item}, error: {e}")
        total_sacos_faltantes += int(item["sacosFaltantes"])
        total_sacos_rotos += int(item["sacosRotos"])  # Contar sacos rotos
        total_sacos_humedos += int(item["sacosHumedos"])  # Contar sacos húmedos
        total_sacos_mojados += int(item["sacosMojados"])  # Contar sacos mojado

        # Evaluar el valor de pagoEstiba
        pago_estiba_value = item.get("pagoEstiba")

        if pago_estiba_value is None:
            print(f"Advertencia: El campo 'pagoEstiba' está vacío para el item {item}")
            continue

        # Caso 1: "No pago 100 bolivianos"
        if "No pago estiba" in pago_estiba_value:
            # Concatenar placaLlegada y pagoEstiba
            # formatted_value = f"{item['placaLlegada']} - {pago_estiba_value}"
            # Agregar el resultado a la lista con un valor calculado
            pago_estiba_list.append({
                "placa": item['placaLlegada'],
                "detalle": pago_estiba_value,
                "monto_descuento": calcular_monto_descuento_estiba(item["sacosDescargados"],item["sacosDescargados"],dataExtra["tipoCambioDescExt"])
            })

        # Caso 2: "Pago parcial"
        elif "Pago parcial" in pago_estiba_value:
            pago_estiba_list.append({
                "placa": item['placaLlegada'],
                "detalle": f"No pago x {item["cantDesc"]}",
                "monto_descuento": calcular_monto_descuento_estiba(item["sacosDescargados"],item["cantDesc"],
                                                                   dataExtra["tipoCambioDescExt"])
            })

    for item in pago_estiba_list:
        total_descuento_estiba += item['monto_descuento']

    datos_de_costo=calcular_costo_por_kg(dataForm["fletePactado"],dataExtra["precioProd"],dataExtra["margenFinanciero"],dataExtra["gastosNacionalizacion"])

    # Calcular la diferencia de peso (diferencia entre salida y llegada)
    diferencia_peso_kg = suma_peso_salida_kg - suma_peso_llegada_kg

    #calcula peso de sacos faltantes
    peso_sacos_faltantes=calcular_peso_no_considerado_por_sacos_faltante(total_sacos_faltantes)

    #calcula la diferencia de peso por cobrar teniendo en cuenta la merma permitida y la cantidad de sacos faltantes
    diferencia_peso_por_cobrar = calcular_diferencia_de_peso_por_cobrar_kg(diferencia_peso_kg, dataExtra["mermaPermitida"],peso_sacos_faltantes )


    # Calcular los descuentos por sacos dañados
    descuento_sacos_rotos = total_sacos_rotos * dataExtra["precioSacosRotos"]
    descuento_sacos_humedos = total_sacos_humedos * dataExtra["precioSacosHumedos"]
    descuento_sacos_mojados = total_sacos_mojados * dataExtra["precioSacosMojados"]

    # Precio base del flete (por tonelada)
    flete_base = dataForm["fletePactado"] * (dataForm["pesoNetoCrt"] / 1000)  # Convertir kg a toneladas

    # Cálculo del precio por tonelada
    precio_por_tonelada = dataExtra["precioProd"] * 1000

    # Sumar flete pactado, margen financiero y gastos de nacionalización
    precio_bruto = precio_por_tonelada + dataForm["fletePactado"] + dataExtra["margenFinanciero"] + dataExtra[
        "gastosNacionalizacion"]

    # Calcular el IGV (18%) sobre el precio bruto
    igv = datos_de_costo.get("igv")

    # Calcular el precio final bruto sumando el IGV
    precio_bruto_final = precio_bruto + igv

    # calcular precio por TM
    precio_por_tonelada_final=round(precio_bruto_final/1.18,2)

    # Paso 2: Calcular el precio por kg
    precio_por_kg = round(precio_bruto_final/1000,4)

    # calcular descuento por sacos faltantes
    total_descuento_sacos_faltantes = round(peso_sacos_faltantes * precio_por_kg,2)

    total_descuento_sacos = calcular_descuento_sacos(total_descuento_sacos_faltantes,descuento_sacos_rotos,descuento_sacos_humedos,descuento_sacos_mojados)

    pago_final = flete_base - total_descuento_sacos

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

    #si hay descuento por sacos faltantes:
    if total_descuento_sacos and total_descuento_sacos > 0:
        pago_final -=total_descuento_sacos

    total_dsct= round((descuento_por_diferencia_peso +total_descuento_estiba + total_descuento_sacos_faltantes + descuento_sacos_rotos + descuento_sacos_humedos + descuento_sacos_mojados),2)

    total_a_pagar= round(flete_base-total_dsct,2)

    total_global_descuentos = round(total_descuento_sacos + total_descuento_estiba + descuento_por_diferencia_peso,2)

    data_procesada={
        "dataForm":dataForm,
        "dataTable":dataTable,
        "dataExtra":dataExtra,
        "procesado": {
            "suma_peso_salida": suma_peso_salida_kg,
            "suma_peso_llegada": suma_peso_llegada_kg,
            "total_sacos_cargados": total_sacos_cargados,
            "total_sacos_descargados": total_sacos_descargados,
            "total_sacos_faltantes": total_sacos_faltantes,
            "total_sacos_rotos": total_sacos_rotos,
            "total_sacos_humedos": total_sacos_humedos,
            "total_sacos_mojados": total_sacos_mojados,
            "total_descuento_estiba": total_descuento_estiba,
            "merma_total": merma_total,
            "diferencia_de_peso":diferencia_peso_kg ,
            'descuento_peso_sacos_faltantes':peso_sacos_faltantes,
            "diferencia_peso_por_cobrar":diferencia_peso_por_cobrar,
            "descuento_por_diferencia_peso":descuento_por_diferencia_peso,
            "descuento_sacos_faltantes": total_descuento_sacos_faltantes,
            "descuento_sacos_rotos": descuento_sacos_rotos,
            "descuento_sacos_humedos":descuento_sacos_humedos,
            "descuento_sacos_mojados":descuento_sacos_mojados,
            "total_descuento_sacos":total_descuento_sacos,
            "total_luego_dsctos_sacos":calcular_monto_luego_dsctos_sacos(flete_base,total_descuento_sacos,descuento_por_diferencia_peso),
            "total_global_descuentos":total_global_descuentos,
            "precio_por_tonelada":round(precio_por_tonelada,2),
            "precio_bruto_final":round(precio_bruto_final,2),
            "precio_por_tonelada_final": precio_por_tonelada_final,
            "precio_por_kg_final":precio_por_kg,
            "pago_final":round(pago_final,2),
            "pago_estiba_list": tuple(pago_estiba_list),
            "igv":round(igv,2),
            "flete_base":round(flete_base,2),
            "empresa": empresa,
            "fecha_numeracion":fecha_numeracion,
            "len_tabla": len(dataTable),
            "len_tabla_one_more":len(dataTable)+1,
            "len_tabla_two_more": len(dataTable)+2,
            "total_dsct":total_dsct,
            "total_a_pagar":total_a_pagar
        }
    }

    return data_procesada