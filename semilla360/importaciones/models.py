from django.db import models

#TABLAS DEL SERVIDOR STARSOFT

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

class OrdenCompraDetStarsoft(models.Model):
    CNUMERO= models.OneToOneField(
        OrdenCompraStarsoft,  # Relación con el modelo principal
        on_delete=models.CASCADE,
        db_column='CNUMERO',  # Coincide con el campo de la tabla
        primary_key=True,
        related_name = 'detalles'
    )
    #cnumero = models.CharField(max_length=13, primary_key=True)
    CNUMIMP = models.CharField(max_length=13, null=True, blank=True)
    CCODPROVE = models.CharField(max_length=11, null=True, blank=True)
    CDESPROVE = models.CharField(max_length=100, null=True, blank=True)
    FEMISION = models.DateTimeField(null=True, blank=True)
    # FENTREGA = models.DateTimeField(null=True, blank=True)
    NIMPORTE = models.FloatField(default=0)
    CCODMONIM = models.CharField(max_length=4, null=True, blank=True)
    NEQUIV_US = models.FloatField(default=0)
    NTIPCAMBI = models.FloatField(default=0)
    CESTADO = models.CharField(max_length=4, null=True, blank=True)
    CLIQADUAN = models.CharField(max_length=20, null=True, blank=True)
    CSOLIINSP = models.CharField(max_length=16, null=True, blank=True)
    CGUIATRAN = models.CharField(max_length=16, null=True, blank=True)
    NLIQVALOR = models.FloatField(default=0)
    LLIQREAL = models.BooleanField(default=False)
    NSALDOTOT = models.FloatField(default=0)
    NSALLIQUI = models.FloatField(default=0)
    COBSERVAC = models.CharField(max_length=100, null=True, blank=True)
    LREAL = models.BooleanField(default=False)
    TIPORDEN = models.CharField(max_length=2, null=True, blank=True)
    CNUMLIQUI = models.CharField(max_length=20, null=True, blank=True)
    NADVALOR = models.FloatField(default=0)
    CVOLANTE = models.CharField(max_length=13, null=True, blank=True)
    CLLAVE = models.CharField(max_length=13, null=True, blank=True)
    CCONVER = models.CharField(max_length=3, null=True, blank=True)
    CPACKING = models.CharField(max_length=13, null=True, blank=True)
    TIPCONVER = models.CharField(max_length=3, null=True, blank=True)
    TIPPREIMP = models.CharField(max_length=3, null=True, blank=True)
    CSITUACION = models.CharField(max_length=2, null=True, blank=True)
    CTERM = models.TextField(null=True, blank=True)
    CFLETE = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    CSEGURO = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    CETAPA = models.CharField(max_length=8, null=True, blank=True)
    CCODCLI = models.CharField(max_length=11, null=True, blank=True)
    CDESCLI = models.CharField(max_length=100, null=True, blank=True)
    CCODMARCA = models.CharField(max_length=20, null=True, blank=True)
    CDESMARCA = models.CharField(max_length=30, null=True, blank=True)
    COD_AUDITORIA = models.CharField(max_length=12, null=True, blank=True)
    CFLETE_MN = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    CSEGURO_MN = models.DecimalField(max_digits=15, decimal_places=6, default=0)
    TIPODOCUMENTO = models.CharField(max_length=2, default='OI')

    class Meta:
        db_table = 'IMPORC'
        managed = False


    def __str__(self):
        return f"{self.cnumero}"


class Proveedor(models.Model):
    PRVCCODIGO = models.CharField(max_length=11, primary_key=True, db_column='PRVCCODIGO')
    PRVCNOMBRE = models.CharField(max_length=100, blank=True, null=True, db_column='PRVCNOMBRE')
    PRVCDIRECC = models.CharField(max_length=100, blank=True, null=True, db_column='PRVCDIRECC')
    PRVCLOCALI = models.CharField(max_length=25, blank=True, null=True, db_column='PRVCLOCALI')
    PRVCPAISAC = models.CharField(max_length=15, blank=True, null=True, db_column='PRVCPAISAC')
    PRVCTELEF1 = models.CharField(max_length=30, blank=True, null=True, db_column='PRVCTELEF1')
    PRVCFAXACR = models.CharField(max_length=15, blank=True, null=True, db_column='PRVCFAXACR')
    PRVCTIPOAC = models.CharField(max_length=2, blank=True, null=True, db_column='PRVCTIPOAC')
    PRVCGIROAC = models.CharField(max_length=2, blank=True, null=True, db_column='PRVCGIROAC')
    PRVCREPRES = models.CharField(max_length=40, blank=True, null=True, db_column='PRVCREPRES')
    PRVCCARREP = models.CharField(max_length=20, blank=True, null=True, db_column='PRVCCARREP')
    PRVCTELREP = models.CharField(max_length=15, blank=True, null=True, db_column='PRVCTELREP')
    PRVDFECCRE = models.DateTimeField(blank=True, null=True, db_column='PRVDFECCRE')
    PRVCUSER = models.CharField(max_length=8, blank=True, null=True, db_column='PRVCUSER')
    PRPVCRUC = models.CharField(max_length=11, blank=True, null=True, db_column='PRPVCRUC')
    PRVCRUC = models.CharField(max_length=11, blank=True, null=True, db_column='PRVCRUC')
    PRVCABREVI = models.CharField(max_length=12, blank=True, null=True, db_column='PRVCABREVI')
    PRVCESTADO = models.CharField(max_length=2, blank=True, null=True, db_column='PRVCESTADO')
    PRVDFECMOD = models.DateTimeField(blank=True, null=True, db_column='PRVDFECMOD')
    PRVEMAIL = models.CharField(max_length=50, blank=True, null=True, db_column='PRVEMAIL')
    PRVCODFAB = models.CharField(max_length=1, blank=True, null=True, db_column='PRVCODFAB')
    PRVPAGO = models.CharField(max_length=4, blank=True, null=True, db_column='PRVPAGO')
    PRVFACTOR = models.DecimalField(max_digits=15, decimal_places=6, blank=True, null=True, db_column='PRVFACTOR')
    PRVGLOSA = models.CharField(max_length=255, blank=True, null=True, db_column='PRVGLOSA')
    PRVREPRESENTANTE = models.CharField(max_length=60, blank=True, null=True, db_column='PRVREPRESENTANTE')
    PRVCONTACTO = models.CharField(max_length=60, blank=True, null=True, db_column='PRVCONTACTO')
    PRVTELREP = models.CharField(max_length=30, blank=True, null=True, db_column='PRVTELREP')
    PRVFAXREP = models.CharField(max_length=30, blank=True, null=True, db_column='PRVFAXREP')
    PRVEMAILREP = models.CharField(max_length=60, blank=True, null=True, db_column='PRVEMAILREP')
    PRVCTIPO_DOCUMENTO = models.CharField(max_length=2, blank=True, null=True, db_column='PRVCTIPO_DOCUMENTO')
    PRVCAPELLIDO_PATERNO = models.CharField(max_length=20, blank=True, null=True, db_column='PRVCAPELLIDO_PATERNO')
    PRVCAPELLIDO_MATERNO = models.CharField(max_length=20, blank=True, null=True, db_column='PRVCAPELLIDO_MATERNO')
    PRVCPRIMER_NOMBRE = models.CharField(max_length=20, blank=True, null=True, db_column='PRVCPRIMER_NOMBRE')
    PRVCSEGUNDO_NOMBRE = models.CharField(max_length=20, blank=True, null=True, db_column='PRVCSEGUNDO_NOMBRE')
    PRVCDOCIDEN = models.CharField(max_length=15, blank=True, null=True, db_column='PRVCDOCIDEN')
    FLGPORTAL_PROVEEDOR = models.BooleanField(blank=True, null=True, db_column='FLGPORTAL_PROVEEDOR')
    FEC_INACTIVO_BLOQUEADO = models.DateTimeField(blank=True, null=True, db_column='FEC_INACTIVO_BLOQUEADO')
    COD_AUDITORIA = models.CharField(max_length=12, blank=True, null=True, db_column='COD_AUDITORIA')
    UBIGEO = models.CharField(max_length=12, blank=True, null=True, db_column='UBIGEO')

    class Meta:
        db_table = 'MAEPROV'
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        managed = False

    def __str__(self):
        return self.prvcnombre or self.prvccodigo


#TABLAS CREADAS EN MYSQL

class Empresa(models.Model):
    nombre_empresa = models.CharField(max_length=255)

    class Meta:
        db_table = 'empresa'

    def __str__(self):
        return self.nombre_empresa


class OrdenCompra(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE,null=True)
    numero_oc = models.CharField(max_length=50,null=True)

    class Meta:
        db_table = 'orden_compra'

    def __str__(self):
        return f"{self.numero_oc} - {self.empresa.nombre_empresa}"


class Producto(models.Model):
    nombre_producto = models.CharField(max_length=255)
    precio_producto = models.DecimalField(max_digits=10, decimal_places=3)

    class Meta:
        db_table = 'producto'

    def __str__(self):
        return self.nombre_producto


class Proveedor_transporte(models.Model):
    nombre_proveedor = models.CharField(max_length=255)

    class Meta:
        db_table = 'proveedor'

    def __str__(self):
        return self.nombre_proveedor


class Transportista(models.Model):
    nombre_transportista = models.CharField(max_length=255)

    class Meta:
        db_table = 'transportista'

    def __str__(self):
        return self.nombre_transportista


class Despacho(models.Model):
    ordenes_compra = models.ManyToManyField(OrdenCompra)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    proveedor = models.ForeignKey(Proveedor_transporte, on_delete=models.CASCADE)
    dua = models.CharField(max_length=50)
    num_recojo = models.CharField(max_length=50, blank=True, null=True)
    fecha_numeracion = models.DateTimeField()
    carta_porte = models.CharField(max_length=50, blank=True, null=True)
    num_factura = models.CharField(max_length=50)
    transportista = models.ForeignKey(Transportista, on_delete=models.CASCADE)
    flete_pactado = models.DecimalField(max_digits=10, decimal_places=2)
    peso_neto_crt = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'despacho'

    def __str__(self):
        return f"Despacho {self.id} - {self.orden_compra.numero_oc}"



class DetalleDespacho(models.Model):
    despacho = models.ForeignKey(Despacho, on_delete=models.CASCADE)
    sacos_cargados = models.IntegerField()
    placa_salida = models.CharField(max_length=10)
    peso_salida = models.DecimalField(max_digits=10, decimal_places=2)
    placa_llegada = models.CharField(max_length=10)
    sacos_descargados = models.IntegerField()
    peso_llegada = models.DecimalField(max_digits=10, decimal_places=2)
    merma = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    sacos_faltantes = models.IntegerField(blank=True, null=True)
    sacos_rotos = models.IntegerField(blank=True, null=True)
    sacos_humedos = models.IntegerField(blank=True, null=True)
    sacos_mojados = models.IntegerField(blank=True, null=True)
    pago_estiba = models.CharField(max_length=50, blank=True, null=True)
    cant_desc = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'detalle_despacho'

    def __str__(self):
        return f"Detalle {self.id} - Vehículo {self.vehiculo.placa}"


class ConfiguracionDespacho(models.Model):
    despacho = models.ForeignKey(Despacho, on_delete=models.CASCADE)
    merma_permitida = models.DecimalField(max_digits=10, decimal_places=2)
    precio_prod = models.DecimalField(max_digits=10, decimal_places=3)
    gastos_nacionalizacion = models.DecimalField(max_digits=10, decimal_places=2)
    margen_financiero = models.DecimalField(max_digits=10, decimal_places=2)
    precio_sacos_rotos = models.DecimalField(max_digits=10, decimal_places=2)
    precio_sacos_humedos = models.DecimalField(max_digits=10, decimal_places=2)
    precio_sacos_mojados = models.DecimalField(max_digits=10, decimal_places=2)
    tipo_cambio_desc_ext = models.DecimalField(max_digits=10, decimal_places=3)

    class Meta:
        db_table = 'configuracion_despacho'

    def __str__(self):
        return f"Configuración para Despacho {self.despacho.id}"