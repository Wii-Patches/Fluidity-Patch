"""The two releases of the game and how to tell them apart."""

# title id (last four bytes, ASCII) -> region key used throughout
TITLES = {'WFLE': 'Fluidity (USA)', 'WFLP': 'Hydroventure (Europe)'}
REGIONS = list(TITLES)
REF = 'WFLE'                 # the release every address was first found in


def region_of_title(title_id):
    """title_id: the 8-byte WAD title id"""
    tag = title_id[4:].decode('ascii', 'replace')
    return tag if tag in TITLES else None
