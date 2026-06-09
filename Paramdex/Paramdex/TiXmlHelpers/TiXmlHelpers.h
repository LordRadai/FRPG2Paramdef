#pragma once
#include <Windows.h>
#include <string>
#include <stringapiset.h>

namespace TiXmlHelpers
{
	// Tinyxml2 uses UTF-8 encoded strings, so we need to convert between std::wstring and std::string, and vice versa.
    inline std::string WToS(const std::wstring& w) 
    {
        return std::string(w.begin(), w.end());
    }

    inline std::wstring SToW(const char* s) 
    {
        if (!s) return L"";
        std::string str(s);
        return std::wstring(str.begin(), str.end());
    }

	inline std::wstring ShiftJisToW(const char* str)
	{
		int len = MultiByteToWideChar(932, 0, str, -1, NULL, 0);
		std::wstring wstr(len, L'\0');
		MultiByteToWideChar(932, 0, str, -1, &wstr[0], len);

		// Remove the null terminator
		if (!wstr.empty() && wstr.back() == L'\0')
			wstr.pop_back();

		return wstr;
	}

	inline std::string ShiftJisToS(const char* str)
	{
		std::string sjis(str);
		// Convert Shift-JIS -> UTF-16
		int wlen = MultiByteToWideChar(932, 0, sjis.c_str(), (int)sjis.size(), NULL, 0);
		std::wstring wstr(wlen, 0);
		MultiByteToWideChar(932, 0, sjis.c_str(), (int)sjis.size(), const_cast<wchar_t*>(wstr.data()), wlen);

		// Convert UTF-16 -> UTF-8
		int u8len = WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), wstr.size(), NULL, 0, NULL, NULL);
		std::string utf8(u8len, 0);
		WideCharToMultiByte(CP_UTF8, 0, wstr.c_str(), wstr.size(), const_cast<char*>(utf8.data()), u8len, NULL, NULL);

		return utf8;
	}

	inline std::string WToShiftJIS(const std::wstring& str)
	{
		int len = WideCharToMultiByte(932, 0, str.c_str(), -1, NULL, 0, NULL, NULL);
		std::string sjis(len, '\0');
		WideCharToMultiByte(932, 0, str.c_str(), -1, &sjis[0], len, NULL, NULL);
		// Remove the null terminator
		if (!sjis.empty() && sjis.back() == '\0')
			sjis.pop_back();
		return sjis;
	}

	inline std::string SToShiftJIS(const std::string& str)
	{
		// Convert UTF-8 -> UTF-16
		int wlen = MultiByteToWideChar(CP_UTF8, 0, str.c_str(), (int)str.size(), NULL, 0);
		std::wstring wstr(wlen, 0);
		MultiByteToWideChar(CP_UTF8, 0, str.c_str(), (int)str.size(), const_cast<wchar_t*>(wstr.data()), wlen);
		// Convert UTF-16 -> Shift-JIS
		int sjislen = WideCharToMultiByte(932, 0, wstr.c_str(), wstr.size(), NULL, 0, NULL, NULL);
		std::string sjis(sjislen, 0);
		WideCharToMultiByte(932, 0, wstr.c_str(), wstr.size(), const_cast<char*>(sjis.data()), sjislen, NULL, NULL);
		return sjis;
	}
}