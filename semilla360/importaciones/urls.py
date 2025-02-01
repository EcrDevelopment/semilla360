from django.core.management.commands.runserver import naiveip_re
from django.urls import path, include
from pandas.conftest import names
from rest_framework.routers import DefaultRouter
from .views import listar_importaciones, registrar_despacho, buscar_orden_importacion, upload_file,upload_file_excel, buscar_proveedor , generar_reporte_base, generar_reporte_detallado,listar_estiba
from graphene_django.views import GraphQLView
from .schema import schema


router = DefaultRouter()
urlpatterns = [
    path('', include(router.urls)),
    path('graphql/', GraphQLView.as_view(graphiql=True, schema=schema)),
    path('lista/', listar_importaciones, name='listar_importaciones'),
    path('buscar_oi/', buscar_orden_importacion, name='buscar_orden_importacion'),
    path('buscar_prov/', buscar_proveedor, name='buscar_proveedor'),
    path('generar_reporte/', generar_reporte_base, name='generar_reporte'),
    path('generar_reporte_detallado/', generar_reporte_detallado, name='generar_reporte'),
    path('registrar-despacho/', registrar_despacho, name='registrar_despacho'),
    path('upload/', upload_file, name='upload_file'),
    path('upload-file-excel/', upload_file_excel, name='upload_file_excel'),
    path('generar-reporte-estiba/',listar_estiba,name='generar_reporte_estiba'),
]


