from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import listar_importaciones, buscar_orden_importacion, upload_file, buscar_proveedor , generar_reporte_dos
from graphene_django.views import GraphQLView
from .schema import schema


router = DefaultRouter()
#router.register(r'product', ProductsModelViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('graphql/', GraphQLView.as_view(graphiql=True, schema=schema)),
    path('lista/', listar_importaciones, name='listar_importaciones'),
    path('buscar_oi/', buscar_orden_importacion, name='buscar_orden_importacion'),
    path('buscar_prov/', buscar_proveedor, name='buscar_proveedor'),
    path('generar_reporte/', generar_reporte_dos, name='generar_reporte'),
    path('upload/', upload_file, name='upload_file'),
]


