
import logging
from typing import Any

from dash import no_update

from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel

logger = logging.getLogger(__name__)
    
def create_text_field_values(
    mm: NewsegsMetaModel,

    generic_text_ids: list[dict[str, Any]],
) -> list[Any]:
    text_values = []
    for text_id in generic_text_ids:
        match text_id.get('key'):
            case 'site-name':
                text_values.append(mm.model.location.name)
            case 'configuration-name':
                text_values.append(mm.name)
            case _:
                text_values.append(no_update)
    return text_values