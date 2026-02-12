import os
import requests

def download_bmw_ca_cert(
    path:str ="BMW_Trusted_Certificates_Latest.pem",
    ca_certificate_url:str = "https://trustbundle.bmwgroup.net/BMW_Trusted_Certificates_Latest.pem"
) -> str:
    """Download the CA certificate from BMW's PKI server.

    This function checks if the CA certificate file already exists at the specified path.
    If it does not exist, it downloads the CA certificate from the specified URL 
    and saves it to the path.

    Args:
        path (str): Specify the path to save the CA certificate file. 
            Default is "BMW_Trusted_Certificates_Latest.pem".
        ca_certificate_url (str): URL to download the CA certificate from. 
            Default is "https://trustbundle.bmwgroup.net/BMW_Trusted_Certificates_Latest.pem".

    Returns:
        str: Path to the downloaded CA certificate file.

    Raises:
        requests.HTTPError: If the request to download the CA certificate fails.
    """
    # already exists, no need to download
    if os.path.exists(path):
        return path

    # download the CA certificate
    response = requests.get(ca_certificate_url)
    response.raise_for_status()

    with open(path, "wb") as f:
        f.write(response.content)

    return path