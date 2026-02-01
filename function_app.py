import azure.functions as func
import logging

app = func.FunctionApp()

# parte quando arriva un messaggio sulla coda 'process-image-queue'
@app.service_bus_queue_trigger(arg_name="msg", 
                               queue_name="process-image-queue", 
                               connection="MY_SERVICEBUS_CONNECTION") 

def process_comic(msg: func.ServiceBusMessage):

    logging.info('Trigger elaborazione fumetto avviato')

    try:
        message_body = msg.get_body().decode('utf-8')
        logging.info(f"Ho ricevuto un messaggio dal cloud: {message_body}")

        
    except Exception as e:
        logging.error(f"Errore durante l'elaborazione del messaggio: {e}")
        raise e