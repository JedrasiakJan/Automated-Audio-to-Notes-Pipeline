import base64
import json
import time
import uuid


def generate_fhir_json(soap_text: str, patient_id: str = "PACJENT-001") -> str:
    encoded_note = base64.b64encode(soap_text.encode("utf-8")).decode("utf-8")

    fhir_resource = {
        "resourceType": "DocumentReference",
        "id": str(uuid.uuid4()),
        "status": "current",
        "type": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "11506-3",
                    "display": "Provider-unspecified Progress note",
                }
            ]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": "Notatka medyczna SafeMed AI",
        "content": [
            {
                "attachment": {
                    "contentType": "text/plain",
                    "data": encoded_note,
                }
            }
        ],
    }

    return json.dumps(fhir_resource, indent=2, ensure_ascii=False)