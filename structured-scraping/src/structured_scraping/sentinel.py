from pathlib import Path 
import logging 

  

logger = logging.getLogger(__name__) 

SENTINEL_SUFFIX = '.inprogress' 


def sentinel_path(output_file: Path) -> Path: 

    """Return path of sentinel file for a given output file.""" 

    return output_file.with_suffix(output_file.suffix + SENTINEL_SUFFIX) 


def write_sentinel(output_file: Path) -> None: 

    """Write sentinel — marks extraction as in-progress.""" 

    sp = sentinel_path(output_file) 

    sp.parent.mkdir(parents=True, exist_ok=True) 

    sp.write_text('inprogress') 

    logger.debug('Sentinel written: %s', sp) 

def remove_sentinel(output_file: Path) -> None: 

    """Remove sentinel — called only after successful extraction.""" 

    sp = sentinel_path(output_file) 

    if sp.exists(): 

        sp.unlink() 

    logger.debug('Sentinel removed: %s', sp) 

  

  

def is_safe_to_process(output_file: Path) -> bool: 

    """ 

    Return True only if the file exists AND no sentinel is present. 

    Sentinel present = extraction crashed or is still running. 

    """ 

    sp = sentinel_path(output_file) 

    if not output_file.exists(): 

        logger.warning('File does not exist: %s', output_file) 

        return False 

    if sp.exists(): 

        logger.warning( 

            'Sentinel found for %s — extraction crashed or is still running.', 

            output_file.name, 

        ) 

        return False 

    return True 

  

  

def get_latest_safe_file(folder: Path, pattern: str = '*.xlsx') -> Path | None: 

    """ 

    Find the most recently modified file in a folder that has no sentinel. 

    Used as a fallback when no explicit path is passed (e.g. manual runs). 

    """ 

    candidates = sorted( 

        folder.glob(pattern), 

        key=lambda f: f.stat().st_mtime, 

        reverse=True, 

    ) 

    for candidate in candidates: 

        if is_safe_to_process(candidate): 

            return candidate 

        logger.info('Skipping %s (sentinel present)', candidate.name) 

    return None 

