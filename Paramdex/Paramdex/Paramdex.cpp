#include <filesystem>
#include <cwctype>

#include "Paramdex.h"
#include "TiXmlHelpers/TiXmlHelpers.h"

#if _MSVC_LANG >= 201703L
#include <filesystem>
namespace fs = std::filesystem;
#else
#include <boost/filesystem.hpp>
namespace fs = boost::filesystem;
#endif

namespace
{
	std::wstring SnakeToPascalCase(const std::wstring& snake) 
	{
		std::wstring pascalStr;
		bool capitalizeNext = true;

		for (wchar_t c : snake) 
		{
			if (c == L'_') 
			{
				capitalizeNext = true;
			}
			else 
			{
				if (capitalizeNext) 
				{
					pascalStr += static_cast<wchar_t>(std::towupper(c));
					capitalizeNext = false;
				}
				else 
				{
					pascalStr += static_cast<wchar_t>(std::towlower(c));
				}
			}
		}

		return pascalStr;
	}
}

namespace Paramdex
{
	int Paramdex::getMemoryRequirements() const
	{
		int total = 0;

		for (const auto& field : m_fields)
			total += field.getMemoryRequirements();

		return total;
	}

	bool Paramdex::loadFromXML(const std::wstring& filePath)
	{
		tinyxml2::XMLDocument doc;

		if (doc.LoadFile(TiXmlHelpers::WToS(filePath).c_str()) != tinyxml2::XML_SUCCESS)
			return false;

		auto* root = doc.RootElement();
		if (!root) return false;

		m_paramType = root->FirstChildElement("ParamType")->GetText();
		m_dataVersion = root->FirstChildElement("DataVersion")->IntText();
		m_bBigEndian = root->FirstChildElement("BigEndian")->BoolText();
		m_bUnicode = root->FirstChildElement("Unicode")->BoolText();
		m_formatVersion = root->FirstChildElement("FormatVersion")->IntText();

		m_fields.clear();

		tinyxml2::XMLElement* fieldsElement = root->FirstChildElement("Fields");

		for (auto* e = fieldsElement->FirstChildElement("Field"); e; e = e->NextSiblingElement("Field"))
		{
			Field field("placeholder", "");
			if (field.loadFromXML(e))
				m_fields.push_back(field);
		}

		return true;
	}

	bool Paramdex::saveToXML(const std::wstring& filePath) const
	{
		tinyxml2::XMLDocument doc;
		auto* decl = doc.NewDeclaration();

		doc.InsertFirstChild(decl);
		auto* root = doc.NewElement("PARAMDEF");
		root->SetAttribute("XmlVersion", 0);

		root->InsertNewChildElement("ParamType")->SetText(m_paramType.c_str());
		root->InsertNewChildElement("DataVersion")->SetText(m_dataVersion);
		root->InsertNewChildElement("BigEndian")->SetText(m_bBigEndian);
		root->InsertNewChildElement("Unicode")->SetText(m_bUnicode);
		root->InsertNewChildElement("Version")->SetText(m_formatVersion);

		doc.InsertEndChild(root);

		tinyxml2::XMLElement* fieldsElement = root->InsertNewChildElement("Fields");

		for (const auto& field : m_fields)
			field.writeXML(fieldsElement);

		return doc.SaveFile(TiXmlHelpers::WToS(filePath).c_str()) == tinyxml2::XML_SUCCESS;
	}

	bool Paramdex::loadEnumsFromDirectory(const std::wstring& directoryPath)
	{
		for (const auto& entry : fs::directory_iterator(directoryPath))
		{
			if (entry.is_regular_file() && entry.path().extension() == L".tdf") 
			{
				std::wstring filename = entry.path().stem().wstring();
				std::wstring enumName = SnakeToPascalCase(filename);

				Enum e;
				if (e.loadFromTdf(entry.path().wstring()))
					m_enums[enumName] = e;
			}
		}

		return true;
	}

	bool Paramdex::saveEnumsToDirectory(const std::wstring& directoryPath) const
	{
		for (const auto& pair : m_enums)
		{
			const std::wstring& enumName = pair.first;
			const auto& e = pair.second;

			std::wstring filename = SnakeToPascalCase(enumName) + L".tdf";
			fs::path filePath = fs::path(directoryPath) / filename;
			e.saveToTdf(filePath.wstring());
		}

		return true;
	}
}