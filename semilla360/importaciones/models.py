from django.db import models

class Product(models.Model):
    nombre = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField()

    class Meta:
        db_table = 'producto'

    def __str__(self):
        return self.name

class OrdenCompra(models.Model):
    nombre = models.CharField(max_length=255)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateField(auto_now_add=True)

    class Meta:
        db_table = 'orden_compra'

    def __str__(self):
        return self.nombre


class OrdenCompraStarsoft(models.Model):
    CNUMERO = models.CharField(max_length=13, primary_key=True)
    CNUMIMP = models.CharField(max_length=13, null=True, blank=True)
    CITEM = models.CharField(max_length=3)
    CCODPROVE = models.CharField(max_length=11, null=True, blank=True)
    FEMISION = models.DateTimeField(null=True, blank=True)
    CCODARTIC = models.CharField(max_length=20, null=True, blank=True)
    CCODREFER = models.CharField(max_length=40, null=True, blank=True)
    CDESARTIC = models.CharField(max_length=200, null=True, blank=True)
    CUNIDAD = models.CharField(max_length=6, null=True, blank=True)
    CUNIREFER = models.CharField(max_length=6, null=True, blank=True)
    NFACTOR = models.FloatField(default=0)
    NCANTIDAD = models.FloatField(default=0)
    NPREUNITA = models.FloatField(default=0)
    NDSCPORCE = models.FloatField(default=0)
    NDESCUENT = models.FloatField(default=0)
    NPRENETO = models.FloatField(default=0)
    NPREREF = models.FloatField(default=0)
    NCANTUNID = models.FloatField(default=0)
    NTOTVENT = models.FloatField(default=0)
    NCANTENTR = models.FloatField(default=0)
    NCANSALDO = models.FloatField(default=0)
    CESTADO = models.CharField(max_length=2, null=True, blank=True)
    NRECIBIDO = models.FloatField(default=0)
    NVALORCIF = models.FloatField(default=0)
    NPORCIF = models.FloatField(default=0)
    NADVALOR = models.FloatField(default=0)
    CLLAVE = models.CharField(max_length=13, null=True, blank=True)
    CMARCA = models.CharField(max_length=1, null=True, blank=True)
    TIPORDEN = models.CharField(max_length=2, null=True, blank=True)
    CCOMENT1 = models.TextField(null=True, blank=True)
    NFACTOR1 = models.FloatField(default=0)
    NCANNAC = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    NFACTORPRV = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    NPRECIODES = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    NTPRECIODES = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    #SALDO_REGDOC = models.DecimalField(max_digits=18, decimal_places=6, default=0)

    class Meta:
        db_table = 'IMPORD'
        managed = False  # Indicamos que Django no debería crear esta tabla


