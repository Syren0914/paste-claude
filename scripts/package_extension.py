"""Build the dependency-free integrated-terminal extension as a local VSIX."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
destination = root / 'dist' / 'paste-claude-native-images-0.3.0.vsix'
destination.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as package:
    package.writestr('[Content_Types].xml', '''<?xml version="1.0"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="json" ContentType="application/json"/>
<Default Extension="js" ContentType="application/javascript"/>
<Default Extension="ps1" ContentType="text/plain"/>
<Default Extension="vsixmanifest" ContentType="text/xml"/>
</Types>''')
    package.writestr('extension.vsixmanifest', '''<?xml version="1.0"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
<Metadata><Identity Language="en-US" Id="paste-claude-native-images" Version="0.3.0" Publisher="paste-claude-local"/>
<DisplayName>Paste Claude: Terminal Screenshots</DisplayName>
<Description xml:space="preserve">Clipboard-preserving screenshot paste for integrated terminals.</Description>
<Tags>terminal,screenshot</Tags><Categories>Other</Categories>
<Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.85.0"/>
<Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="ui"/></Properties></Metadata>
<Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation><Dependencies/>
<Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/></Assets>
</PackageManifest>''')
    for source in (root / 'vscode-extension').iterdir():
        if source.is_file():
            package.write(source, 'extension/' + source.name)
print(destination)
