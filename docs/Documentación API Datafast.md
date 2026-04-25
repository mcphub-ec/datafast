# **Documentación API Datafast (Dataweb) para Servidor MCP**

Esta documentación técnica detalla el funcionamiento de la API REST de Datafast (Ecuador), diseñada para ser utilizada en la creación de un servidor Model Context Protocol (MCP).

## **1\. Arquitectura y Configuración Base**

Datafast utiliza el motor de pagos de ACI Worldwide (Oppwa). El flujo de pago e-commerce estándar se divide en dos pasos: preparación (Checkout) y renderizado/cobro mediante un widget (frontend).

* **URL Base (Producción):** https://eu-prod.oppwa.com  
* **URL Base (Sandbox/Pruebas):** https://eu-test.oppwa.com  
* **Formato de Petición (CRÍTICO):** Las peticiones POST y DELETE **NO utilizan JSON**. Deben enviarse obligatoriamente como application/x-www-form-urlencoded. Las peticiones GET envían sus parámetros en la URL (Query Params).

### **Autenticación y Credenciales**

Datafast requiere dos identificadores clave en casi todas las peticiones:

1. **Header de Autorización:** Authorization: Bearer \<TU\_TOKEN\_BEARER\>  
2. **Identificador de Entidad (entityId):** Un código alfanumérico que representa la cuenta del comercio. Se envía como un parámetro más en el cuerpo o URL de la petición. *(Nota: En Datafast a veces te entregan un entityId distinto para Visa/MC y otro para Diners/Discover).*

## **2\. Flujo Principal de Pagos**

### **Paso 1: Generar CheckoutId (POST /v1/checkouts)**

* **Propósito:** Prepara la transacción y obtiene un ID único temporal (checkoutId) que se usará para renderizar el formulario en el frontend del cliente.  
* **Estructura de Impuestos (Ecuador):** El monto total (amount) debe coincidir exactamente con la suma de los valores desglosados enviados en el array customParameters.  
  * customParameters\[SHOPPER\_VAL\_BASE0\]: Subtotal IVA 0%  
  * customParameters\[SHOPPER\_VAL\_BASEIMP\]: Subtotal Gravado  
  * customParameters\[SHOPPER\_VAL\_IVA\]: Valor del IVA  
  * customParameters\[SHOPPER\_VAL\_ICE\]: Valor del ICE

### **Paso 2: Verificar Estado (GET /v1/checkouts/{checkoutId}/payment)**

* **Propósito:** Una vez el cliente ingresa su tarjeta en el widget de Datafast, el comercio debe consultar este endpoint para validar si la transacción fue aprobada o rechazada.  
* **Parámetros obligatorios:** entityId.

## **3\. Endpoints Secundarios y Avanzados**

### **3.1. Reversos y Anulaciones (POST /v1/payments/{paymentId})**

* **Propósito:** Permite reversar (Void) o reembolsar (Refund) una transacción aprobada.  
* **Parámetros:** Requiere el paymentId (obtenido en el status), entityId, amount, currency y el paymentType.  
* **Tipos de Pago (paymentType):** RV (Reversal/Anulación, solo el mismo día) o RF (Refund/Reembolso).

### **3.2. Consulta por ID del Comercio (GET /v1/query)**

* **Propósito:** Permite buscar el estado de una transacción utilizando tu propio número de orden (merchantTransactionId) en lugar del checkoutId.

### **3.3. Pagos Recurrentes / OneClick (POST /v1/registrations/{registrationId}/payments)**

* **Propósito:** Realiza un cargo automático a una tarjeta que fue guardada (tokenizada) previamente por el cliente.  
* **ID de Registro (registrationId):** Es el token seguro de la tarjeta.

### **3.4. Eliminar Tarjeta Guardada (DELETE /v1/registrations/{registrationId})**

* **Propósito:** Elimina un token de tarjeta para que no pueda volver a ser cobrada.

## **4\. Códigos de Resultado Comunes (result.code)**

Datafast utiliza expresiones regulares para sus códigos de respuesta.

* 000.000.000 o 000.100.112: Transacción exitosa / Aprobada.  
* 800.100.152 o 800.100.162: Transacción rechazada (Declinada por el banco).  
* 100.400.500: Error de sintaxis o datos inválidos en la petición (Revisar sumatoria de impuestos).