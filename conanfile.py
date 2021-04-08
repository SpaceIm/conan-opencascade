from conans import ConanFile, CMake, tools
from conans.errors import ConanInvalidConfiguration
import os
import textwrap

required_conan_version = ">=1.33.0"


class OpenCascadeConan(ConanFile):
    name = "opencascade"
    description = "A software development platform providing services for 3D " \
                  "surface and solid modeling, CAD data exchange, and visualization."
    homepage = "https://dev.opencascade.org"
    url = "https://github.com/conan-io/conan-center-index"
    license = "LGPL-2.1-or-later"
    topics = ("conan", "opencascade", "occt", "3d", "modeling", "cad")

    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "with_ffmpeg": [True, False],
        "with_freeimage": [True, False],
        "with_openvr": [True, False],
        "with_rapidjson": [True, False],
        "with_tbb": [True, False],
    }
    default_options = {
        "shared": False,
        "fPIC": True,
        "with_ffmpeg": False,
        "with_freeimage": False,
        "with_openvr": False,
        "with_rapidjson": False,
        "with_tbb": False,
    }

    short_paths = True

    generators = "cmake"
    _cmake = None

    @property
    def _source_subfolder(self):
        return "source_subfolder"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.fPIC

    def configure(self):
        if self.options.shared:
            del self.options.fPIC

    def requirements(self):
        self.requires("tcl/8.6.10")
        self.requires("tk/8.6.10")
        self.requires("freetype/2.10.4")
        self.requires("opengl/system")
        if self._depends_on_fontconfig:
            self.requires("fontconfig/2.13.93")
        # TODO: add ffmpeg & freeimage support
        if self.options.with_ffmpeg:
            raise ConanInvalidConfiguration("ffmpeg recipe not yet available in CCI")
        if self.options.with_freeimage:
            raise ConanInvalidConfiguration("freeimage recipe not yet available in CCI")
        if self.options.with_openvr:
            self.requires("openvr/1.14.15")
        if self.options.with_rapidjson:
            self.requires("rapidjson/1.1.0")
        if self.options.with_tbb:
            self.requires("tbb/2020.3")

    @property
    def _depends_on_fontconfig(self):
        return not (self.settings.os in ["Windows", "Android"] or tools.is_apple_os(self.settings.os))

    def validate(self):
        if self.settings.compiler == "clang" and self.settings.compiler.version == "6.0" and \
           self.settings.build_type == "Release":
            raise ConanInvalidConfiguration("OpenCASCADE {} doesn't support Clang 6.0.".format(self.version))

    def source(self):
        tools.get(**self.conan_data["sources"][self.version])
        extracted_dir = "OCCT-" + self.version.replace(".", "_")
        tools.rename(extracted_dir, self._source_subfolder)

    def _patch_sources(self):
        cmakelists = os.path.join(self._source_subfolder, "CMakeLists.txt")
        occ_toolkit_cmake = os.path.join(self._source_subfolder, "adm", "cmake", "occt_toolkit.cmake")
        occ_csf_cmake = os.path.join(self._source_subfolder, "adm", "cmake", "occt_csf.cmake")

        # Inject conanbuildinfo, upstream build files are not ready for a CMake wrapper (too much modifications required)
        tools.replace_in_file(
            cmakelists,
            "project (OCCT)",
            '''project (OCCT)
                include(${CMAKE_BINARY_DIR}/conanbuildinfo.cmake)
                conan_basic_setup(TARGETS)''')

        # Avoid to add system include/libs directories
        tools.replace_in_file(cmakelists, "${3RDPARTY_INCLUDE_DIRS}", "${CONAN_INCLUDE_DIRS}")
        tools.replace_in_file(cmakelists, "${3RDPARTY_LIBRARY_DIRS}", "${CONAN_LIB_DIRS}")

        # Do not fail due to "fragile" upstream logic to find dependencies
        tools.replace_in_file(cmakelists, "if (3RDPARTY_NO_LIBS)", "if(0)")
        tools.replace_in_file(cmakelists, "if (3RDPARTY_NO_DLLS)", "if(0)")

        # Inject dependencies from conan, and avoid to link hardcoded libs
        # (for example we don't want to link freetype.lib on Windows if Debug, but freetyped.lib)
        conan_targets = ["CONAN_PKG::tcl", "CONAN_PKG::tk", "CONAN_PKG::freetype"]

        ## freetype
        tools.replace_in_file(
            occ_csf_cmake,
            "set (CSF_FREETYPE \"freetype\")",
            "set (CSF_FREETYPE \"{}\")".format(" ".join(self.deps_cpp_info["freetype"].libs)))
        ## tcl
        tcl_libs = self.deps_cpp_info["tcl"].libs
        tcl_lib = next(filter(lambda lib: "tcl8" in lib, tcl_libs))
        tools.replace_in_file(
            os.path.join(self._source_subfolder, "adm", "cmake", "tcl.cmake"),
            "${CSF_TclLibs}",
            tcl_lib)
        ## tk
        tk_libs = self.deps_cpp_info["tk"].libs
        tk_lib = next(filter(lambda lib: "tk8" in lib, tk_libs))
        tools.replace_in_file(
            os.path.join(self._source_subfolder, "adm", "cmake", "tk.cmake"),
            "${CSF_TclTkLibs}",
            tk_lib)
        ## fontconfig
        if self._depends_on_fontconfig:
            tools.replace_in_file(
                occ_csf_cmake,
                "set (CSF_fontconfig  \"fontconfig\")",
                "set (CSF_fontconfig  \"{}\")".format(" ".join(self.deps_cpp_info["fontconfig"].libs)))
        ## tbb
        if self.options.with_tbb:
            conan_targets.append("CONAN_PKG::tbb")
            tools.replace_in_file(
                occ_csf_cmake,
                "set (CSF_TBB \"tbb tbbmalloc\")",
                "set (CSF_TBB \"{}\")".format(" ".join(self.deps_cpp_info["tbb"].libs)))
        ## ffmpeg
        if self.options.with_ffmpeg:
            conan_targets.append("CONAN_PKG::ffmpeg")
            tools.replace_in_file(
                occ_csf_cmake,
                "set (CSF_FFmpeg \"avcodec avformat swscale avutil\")",
                "set (CSF_FFmpeg \"{}\")".format(" ".join(self.deps_cpp_info["ffmpeg"].libs)))
        ## freeimage
        if self.options.with_freeimage:
            conan_targets.append("CONAN_PKG::freeimage")
            tools.replace_in_file(
                occ_csf_cmake,
                "set (CSF_FreeImagePlus \"freeimage\")",
                "set (CSF_FreeImagePlus \"{}\")".format(" ".join(self.deps_cpp_info["freeimage"].libs)))
        ## openvr
        if self.options.with_openvr:
            conan_targets.append("CONAN_PKG::openvr")
            tools.replace_in_file(
                occ_csf_cmake,
                "set (CSF_OpenVR \"openvr_api\")",
                "set (CSF_OpenVR \"{}\")".format(" ".join(self.deps_cpp_info["openvr"].libs)))
        ## don't force link libstdc++, honor settings.compiler.libcxx
        tools.replace_in_file(
            occ_csf_cmake,
            "set (CSF_ThreadLibs  \"pthread rt stdc++\")",
            "set (CSF_ThreadLibs  \"pthread rt\")")

        ## Inject conan targets
        tools.replace_in_file(
            occ_toolkit_cmake,
            "${USED_EXTERNAL_LIBS_BY_CURRENT_PROJECT}",
            "${{USED_EXTERNAL_LIBS_BY_CURRENT_PROJECT}} {}".format(" ".join(conan_targets)))

        # Do not install pdb files
        tools.replace_in_file(
            occ_toolkit_cmake,
            """    install (FILES  ${CMAKE_BINARY_DIR}/${OS_WITH_BIT}/${COMPILER}/bin\\${OCCT_INSTALL_BIN_LETTER}/${PROJECT_NAME}.pdb
             CONFIGURATIONS Debug RelWithDebInfo
             DESTINATION "${INSTALL_DIR_BIN}\\${OCCT_INSTALL_BIN_LETTER}")""",
            "")

        # No hardcoded link through #pragma
        tools.replace_in_file(
            os.path.join(self._source_subfolder, "src", "Font", "Font_FontMgr.cxx"),
            "#pragma comment (lib, \"freetype.lib\")",
            "")
        tools.replace_in_file(
            os.path.join(self._source_subfolder, "src", "Draw", "Draw.cxx"),
            """#pragma comment (lib, "tcl" STRINGIZE2(TCL_MAJOR_VERSION) STRINGIZE2(TCL_MINOR_VERSION) ".lib")
#pragma comment (lib, "tk"  STRINGIZE2(TCL_MAJOR_VERSION) STRINGIZE2(TCL_MINOR_VERSION) ".lib")""",
            ""
        )

    def _configure_cmake(self):
        if self._cmake:
            return self._cmake
        self._cmake = CMake(self)
        self._cmake.definitions["3RDPARTY_TCL_LIBRARY_DIR"] = \
            os.path.join(self.deps_cpp_info["tcl"].rootpath, "lib")
        self._cmake.definitions["3RDPARTY_TCL_INCLUDE_DIR"] = \
            self.deps_cpp_info["tcl"].include_paths[0]
        self._cmake.definitions["3RDPARTY_TK_LIBRARY_DIR"] = \
            os.path.join(self.deps_cpp_info["tk"].rootpath, "lib")
        self._cmake.definitions["3RDPARTY_TK_INCLUDE_DIR"] = \
            self.deps_cpp_info["tk"].include_paths[0]
        if not self.options.shared:
            self._cmake.definitions["BUILD_LIBRARY_TYPE"] = "Static"

        self._cmake.definitions["INSTALL_DIR_BIN"] = "bin"
        self._cmake.definitions["INSTALL_DIR_INCLUDE"] = "include"
        self._cmake.definitions["INSTALL_DIR_LIB"] = "lib"
        self._cmake.definitions["INSTALL_DIR_RESOURCE"] = "res/resource"
        self._cmake.definitions["INSTALL_DIR_DATA"] = "res/data"
        self._cmake.definitions["INSTALL_DIR_SAMPLES"] = "res/samples"
        self._cmake.definitions["INSTALL_DIR_DOC"] = "res/doc"
        self._cmake.definitions["INSTALL_DIR_LAYOUT"] = "Unix"

        self._cmake.definitions["BUILD_DOC_Overview"] = False

        self._cmake.definitions["USE_FREEIMAGE"] = self.options.with_freeimage
        self._cmake.definitions["USE_OPENVR"] = self.options.with_openvr
        self._cmake.definitions["USE_FFMPEG"] = self.options.with_ffmpeg
        self._cmake.definitions["USE_TBB"] = self.options.with_tbb
        self._cmake.definitions["USE_RAPIDJSON"] = self.options.with_rapidjson

        self._cmake.configure(source_folder=self._source_subfolder)
        return self._cmake

    def build(self):
        self._patch_sources()
        cmake = self._configure_cmake()
        cmake.build()

    def _replace_package_folder(self, source, target):
        new_name = ""
        if os.path.isdir(os.path.join(self.package_folder, source)):
            tools.rmdir(os.path.join(self.package_folder, target))
            tools.rename(
                os.path.join(self.package_folder, source),
                os.path.join(self.package_folder, target))

    def package(self):
        cmake = self._configure_cmake()
        cmake.install()
        self.copy(
            "LICENSE_LGPL_21.txt",
            src=self._source_subfolder,
            dst="licenses")
        self.copy(
            "OCCT_LGPL_EXCEPTION.txt",
            src=self._source_subfolder,
            dst="licenses")
        tools.rmdir(os.path.join(self.package_folder, "cmake"))
        tools.rmdir(os.path.join(self.package_folder, "lib", "cmake"))
        if self.settings.build_type == "Debug":
            self._replace_package_folder("libd", "lib")
            self._replace_package_folder("bind", "bin")
        elif self.settings.build_type == "RelWithDebInfo":
            self._replace_package_folder("libi", "lib")
            self._replace_package_folder("bini", "bin")

        self._create_cmake_module_alias_targets(
            os.path.join(self.package_folder, self._module_file_rel_path),
            {target: "OpenCASCADE::{}".format(target) for module in self._modules_toolkits.values() for target in module}
        )

    @staticmethod
    def _create_cmake_module_alias_targets(module_file, targets):
        content = ""
        for alias, aliased in targets.items():
            content += textwrap.dedent("""\
                if(TARGET {aliased} AND NOT TARGET {alias})
                    add_library({alias} INTERFACE IMPORTED)
                    set_property(TARGET {alias} PROPERTY INTERFACE_LINK_LIBRARIES {aliased})
                endif()
            """.format(alias=alias, aliased=aliased))
        tools.save(module_file, content)

    @property
    def _module_subfolder(self):
        return os.path.join("lib", "cmake")

    @property
    def _module_file_rel_path(self):
        return os.path.join(self._module_subfolder,
                            "conan-official-{}-targets.cmake".format(self.name))

    @property
    def _modules_toolkits(self):
        return {
            "FoundationClasses": {
                "TKernel": [],
                "TKMath": ["TKernel"],
            },
            "ModelingData": {
                "TKG2d": ["TKernel", "TKMath"],
                "TKG3d": ["TKMath", "TKernel", "TKG2d"],
                "TKGeomBase": ["TKernel", "TKMath", "TKG2d", "TKG3d"],
                "TKBRep": ["TKMath", "TKernel", "TKG2d", "TKG3d", "TKGeomBase"],
            },
            "ModelingAlgorithms": {
                "TKGeomAlgo": ["TKernel", "TKMath", "TKG3d", "TKG2d", "TKGeomBase", "TKBRep"],
                "TKTopAlgo": ["TKMath", "TKernel", "TKG2d", "TKG3d", "TKGeomBase", "TKBRep", "TKGeomAlgo"],
                "TKPrim": ["TKBRep", "TKernel", "TKMath", "TKG2d", "TKGeomBase", "TKG3d", "TKTopAlgo"],
                "TKBO": ["TKBRep", "TKTopAlgo", "TKMath", "TKernel", "TKG2d", "TKG3d", "TKGeomAlgo", "TKGeomBase",
                         "TKPrim", "TKShHealing"],
                "TKBool": ["TKBRep", "TKTopAlgo", "TKMath", "TKernel", "TKPrim", "TKG2d", "TKG3d", "TKShHealing",
                           "TKGeomBase", "TKGeomAlgo", "TKBO"],
                "TKHLR": ["TKBRep", "TKernel", "TKMath", "TKGeomBase", "TKG2d", "TKG3d", "TKGeomAlgo", "TKTopAlgo"],
                "TKFillet": ["TKBRep", "TKernel", "TKMath", "TKGeomBase", "TKGeomAlgo", "TKG2d", "TKTopAlgo", "TKG3d",
                             "TKBool", "TKShHealing", "TKBO"],
                "TKOffset": ["TKFillet", "TKBRep", "TKTopAlgo", "TKMath", "TKernel", "TKGeomBase", "TKG2d", "TKG3d",
                             "TKGeomAlgo", "TKShHealing", "TKBO", "TKPrim", "TKBool"],
                "TKFeat": ["TKBRep", "TKTopAlgo", "TKGeomAlgo", "TKMath", "TKernel", "TKGeomBase", "TKPrim", "TKG2d",
                           "TKBO", "TKG3d", "TKBool", "TKShHealing"],
                "TKMesh": ["TKernel", "TKMath", "TKBRep", "TKTopAlgo", "TKShHealing", "TKGeomBase", "TKG3d", "TKG2d"],
                "TKXMesh": ["TKBRep", "TKMath", "TKernel", "TKG2d", "TKG3d", "TKMesh"],
                "TKShHealing": ["TKBRep", "TKernel", "TKMath", "TKG2d", "TKTopAlgo", "TKG3d", "TKGeomBase",
                                "TKGeomAlgo"],
            },
            "Visualization": {
                "TKService": ["TKernel", "TKMath"],
                "TKV3d": ["TKBRep", "TKMath", "TKernel", "TKService", "TKShHealing", "TKTopAlgo", "TKG2d", "TKG3d",
                          "TKGeomBase", "TKMesh", "TKGeomAlgo", "TKHLR"],
                "TKOpenGl": ["TKernel", "TKService", "TKMath"],
                "TKMeshVS": ["TKV3d", "TKMath", "TKService", "TKernel", "TKG3d", "TKG2d"],
            },
            "ApplicationFramework": {
                "TKCDF": ["TKernel"],
                "TKLCAF": ["TKCDF", "TKernel"],
                "TKCAF": ["TKernel", "TKGeomBase", "TKBRep", "TKTopAlgo", "TKMath", "TKG2d", "TKG3d", "TKCDF",
                          "TKLCAF", "TKBO"],
                "TKBinL": ["TKCDF", "TKernel", "TKLCAF"],
                "TKXmlL": ["TKCDF", "TKernel", "TKMath", "TKLCAF"],
                "TKBin": ["TKBRep", "TKMath", "TKernel", "TKG2d", "TKG3d", "TKCAF", "TKCDF", "TKLCAF", "TKBinL"],
                "TKXml": ["TKCDF", "TKernel", "TKMath", "TKBRep", "TKG2d", "TKGeomBase", "TKG3d", "TKLCAF", "TKCAF",
                          "TKXmlL"],
                "TKStdL": ["TKernel", "TKCDF", "TKLCAF"],
                "TKStd": ["TKernel", "TKCDF", "TKCAF", "TKLCAF", "TKBRep", "TKMath", "TKG2d", "TKG3d", "TKStdL"],
                "TKTObj": ["TKCDF", "TKernel", "TKMath", "TKLCAF"],
                "TKBinTObj": ["TKCDF", "TKernel", "TKTObj", "TKMath", "TKLCAF", "TKBinL"],
                "TKXmlTObj": ["TKCDF", "TKernel", "TKTObj", "TKMath", "TKLCAF", "TKXmlL"],
                "TKVCAF": ["TKernel", "TKGeomBase", "TKBRep", "TKTopAlgo", "TKMath", "TKService", "TKG2d", "TKG3d",
                           "TKCDF", "TKLCAF", "TKBO", "TKCAF", "TKV3d"],
            },
            "DataExchange": {
                "TKXSBase": ["TKBRep", "TKernel", "TKMath", "TKG2d", "TKG3d", "TKTopAlgo", "TKGeomBase", "TKShHealing"],
                "TKSTEPBase": ["TKernel", "TKXSBase", "TKMath"],
                "TKSTEPAttr": ["TKernel", "TKXSBase", "TKSTEPBase"],
                "TKSTEP209": ["TKernel", "TKXSBase", "TKSTEPBase"],
                "TKSTEP": ["TKernel", "TKSTEPAttr", "TKSTEP209", "TKSTEPBase", "TKBRep", "TKMath", "TKG2d",
                           "TKShHealing", "TKTopAlgo", "TKG3d", "TKGeomBase", "TKGeomAlgo", "TKXSBase"],
                "TKIGES": ["TKBRep", "TKernel", "TKMath", "TKTopAlgo", "TKShHealing", "TKG2d", "TKG3d", "TKGeomBase",
                           "TKGeomAlgo", "TKPrim", "TKBool", "TKXSBase"],
                "TKXCAF": ["TKBRep", "TKernel", "TKMath", "TKService", "TKG2d", "TKTopAlgo", "TKV3d", "TKCDF", "TKLCAF",
                           "TKG3d", "TKCAF", "TKVCAF"],
                "TKXDEIGES": ["TKBRep", "TKernel", "TKMath", "TKXSBase", "TKCDF", "TKLCAF", "TKG2d", "TKG3d", "TKXCAF",
                              "TKIGES"],
                "TKXDESTEP": ["TKBRep", "TKSTEPAttr", "TKernel", "TKMath", "TKXSBase", "TKTopAlgo", "TKG2d", "TKCAF",
                              "TKSTEPBase", "TKCDF", "TKLCAF", "TKG3d", "TKXCAF", "TKSTEP", "TKShHealing"],
                "TKSTL": ["TKernel", "TKMath", "TKBRep", "TKG2d", "TKG3d", "TKTopAlgo"],
                "TKVRML": ["TKBRep", "TKTopAlgo", "TKMath", "TKGeomBase", "TKernel", "TKPrim", "TKG2d", "TKG3d",
                           "TKMesh", "TKHLR", "TKService", "TKGeomAlgo", "TKV3d", "TKLCAF", "TKXCAF"],
                "TKXmlXCAF": ["TKXmlL", "TKBRep", "TKCDF", "TKMath", "TKernel", "TKService", "TKG2d", "TKGeomBase",
                              "TKCAF", "TKG3d", "TKLCAF", "TKXCAF", "TKXml"],
                "TKBinXCAF": ["TKBRep", "TKXCAF", "TKMath", "TKService", "TKernel", "TKBinL", "TKG2d", "TKCAF", "TKCDF",
                              "TKG3d", "TKLCAF", "TKBin"],
                "TKRWMesh": ["TKernel", "TKMath", "TKMesh", "TKXCAF", "TKLCAF", "TKV3d", "TKBRep", "TKG3d",
                             "TKService"],
            },
            "Draw": {
                "TKDraw": ["TKernel", "TKG2d", "TKGeomBase", "TKG3d", "TKMath", "TKBRep", "TKGeomAlgo", "TKTopAlgo",
                           "TKShHealing", "TKMesh", "TKService", "TKHLR"],
                "TKTopTest": ["TKBRep", "TKGeomAlgo", "TKTopAlgo", "TKernel", "TKMath", "TKBO", "TKG2d", "TKG3d",
                              "TKDraw", "TKHLR", "TKGeomBase", "TKMesh", "TKService", "TKV3d", "TKFillet", "TKPrim",
                              "TKBool", "TKOffset", "TKFeat", "TKShHealing"],
                "TKViewerTest": ["TKGeomBase", "TKFillet", "TKBRep", "TKTopAlgo", "TKHLR", "TKernel", "TKMath",
                                 "TKService", "TKShHealing", "TKBool", "TKPrim", "TKGeomAlgo", "TKG2d", "TKTopTest",
                                 "TKG3d", "TKOffset", "TKMesh", "TKV3d", "TKDraw", "TKOpenGl"],
                "TKXSDRAW": ["TKBRep", "TKV3d", "TKMath", "TKernel", "TKService", "TKXSBase", "TKMeshVS", "TKG3d",
                             "TKViewerTest", "TKG2d", "TKSTEPBase", "TKTopAlgo", "TKGeomBase", "TKGeomAlgo", "TKMesh",
                             "TKDraw", "TKSTEP", "TKIGES", "TKSTL", "TKVRML", "TKLCAF", "TKDCAF", "TKXCAF", "TKRWMesh"],
                "TKDCAF": ["TKGeomBase", "TKBRep", "TKGeomAlgo", "TKernel", "TKMath", "TKG2d", "TKG3d", "TKDraw",
                           "TKCDF", "TKV3d", "TKService", "TKLCAF", "TKFillet", "TKTopAlgo", "TKPrim", "TKBool",
                           "TKBO", "TKCAF", "TKVCAF", "TKViewerTest", "TKStd", "TKStdL", "TKBin", "TKBinL", "TKXml",
                           "TKXmlL"],
                "TKXDEDRAW": ["TKCDF", "TKBRep", "TKXCAF", "TKernel", "TKIGES", "TKV3d", "TKMath", "TKService",
                              "TKXSBase", "TKG2d", "TKCAF", "TKVCAF", "TKDraw", "TKTopAlgo", "TKLCAF", "TKG3d",
                              "TKSTEPBase", "TKSTEP", "TKMesh", "TKXSDRAW", "TKXDEIGES", "TKXDESTEP", "TKDCAF",
                              "TKViewerTest", "TKBinXCAF", "TKXmlXCAF", "TKVRML"],
                "TKTObjDRAW": ["TKernel", "TKCDF", "TKLCAF", "TKTObj", "TKMath", "TKDraw", "TKDCAF", "TKBinTObj",
                               "TKXmlTObj"],
                "TKQADraw": ["TKBRep", "TKMath", "TKernel", "TKService", "TKG2d", "TKDraw", "TKV3d", "TKGeomBase",
                              "TKG3d", "TKViewerTest", "TKCDF", "TKDCAF", "TKLCAF", "TKFillet", "TKTopAlgo", "TKHLR",
                              "TKBool", "TKGeomAlgo", "TKPrim", "TKBO", "TKShHealing", "TKOffset", "TKFeat", "TKCAF",
                              "TKVCAF", "TKIGES", "TKXSBase", "TKMesh", "TKXCAF", "TKBinXCAF", "TKSTEP", "TKSTEPBase",
                              "TKXDESTEP", "TKXSDRAW", "TKSTL", "TKXml", "TKTObj", "TKXmlL", "TKBin", "TKBinL", "TKStd",
                              "TKStdL"],
            },
        }

    def package_info(self):
        self.cpp_info.names["cmake_find_package"] = "OpenCASCADE"
        self.cpp_info.names["cmake_find_package_multi"] = "OpenCASCADE"

        for component, targets in self._modules_toolkits.items():
            conan_component_name = "occt_{}".format(component.lower())
            self.cpp_info.components[conan_component_name].names["cmake_find_package"] = component
            self.cpp_info.components[conan_component_name].names["cmake_find_package_multi"] = component
            for target_lib, internal_requires in targets.items():
                conan_component_target_name = "occt_{}".format(target_lib.lower())
                target_requires = ["occt_{}".format(inter_require.lower()) for inter_require in internal_requires]
                self.cpp_info.components[conan_component_target_name].names["cmake_find_package"] = target_lib
                self.cpp_info.components[conan_component_target_name].names["cmake_find_package_multi"] = target_lib
                self.cpp_info.components[conan_component_target_name].builddirs.append(self._module_subfolder)
                self.cpp_info.components[conan_component_target_name].build_modules["cmake_find_package"] = [self._module_file_rel_path]
                self.cpp_info.components[conan_component_target_name].build_modules["cmake_find_package_multi"] = [self._module_file_rel_path]
                self.cpp_info.components[conan_component_target_name].libs = [target_lib]
                self.cpp_info.components[conan_component_target_name].requires = target_requires
                if self.settings.os == "Windows" and not self.options.shared:
                    self.cpp_info.components[conan_component_target_name].defines.append("OCCT_STATIC_BUILD")
                self.cpp_info.components[conan_component_name].requires.append(conan_component_target_name)

        # 3rd-party requirements taken from https://dev.opencascade.org/doc/overview/html/index.html#intro_req_libs
        ## TKBO
        if self.options.with_tbb:
            self.cpp_info.components["occt_tkbo"].requires.append("tbb::tbb")

        ## TKDraw
        self.cpp_info.components["occt_tkdraw"].requires.extend(["tcl::tcl", "tk::tk"])
        if self.options.with_tbb:
            self.cpp_info.components["occt_tkdraw"].requires.append("tbb::tbb")
        ### and XwLibs?
        if self.settings.os == "Windows":
            self.cpp_info.components["occt_tkdraw"].system_libs.extend(["gdi32", "advapi32", "user32", "shell32"])
        elif tools.is_apple_os(self.settings.os):
            self.cpp_info.components["occt_tkdraw"].frameworks.extend(["Appkit", "IOKit"])

        ## TKernel
        if self.options.with_tbb:
            self.cpp_info.components["occt_tkernel"].requires.append("tbb::tbb")
        if self.settings.os == "Linux":
            self.cpp_info.components["occt_tkernel"].system_libs.extend(["dl", "pthread", "rt"])
        elif self.settings.os == "Android":
            self.cpp_info.components["occt_tkernel"].system_libs.append("log")
        elif self.settings.os == "Windows":
            self.cpp_info.components["occt_tkernel"].system_libs.extend(["advapi32", "gdi32", "psapi", "user32", "wsock32"])

        ## TKGeomBase
        if self.options.with_tbb:
            self.cpp_info.components["occt_tkgeombase"].requires.append("tbb::tbb")

        ## TKMath
        if self.options.with_tbb:
            self.cpp_info.components["occt_tkmath"].requires.append("tbb::tbb")

        ## TKOpenGl
        self.cpp_info.components["occt_tkopengl"].requires.extend(["freetype::freetype", "opengl::opengl"])
        if self.options.with_tbb:
            self.cpp_info.components["occt_tkopengl"].requires.append("tbb::tbb")
        ### and XwLibs?
        if self.settings.os == "Windows":
            self.cpp_info.components["occt_tkopengl"].system_libs.extend(["gdi32", "user32"])
        elif tools.is_apple_os(self.settings.os):
            self.cpp_info.components["occt_tkopengl"].frameworks.extend(["Appkit", "IOKit"])

        ## TKQADraw
        if self.options.with_tbb:
            self.cpp_info.components["occt_tkqadraw"].requires.append("tbb::tbb")
        if self.settings.os == "Windows":
            self.cpp_info.components["occt_tkqadraw"].system_libs.extend(["advapi32", "gdi32", "user32"])

        ## TKRWMesh
        if self.options.with_rapidjson:
            self.cpp_info.components["occt_tkrwmesh"].requires.append("rapidjson::rapidjson")

        ## TKService
        self.cpp_info.components["occt_tkservice"].requires.extend(["freetype::freetype", "opengl::opengl"])
        if self._depends_on_fontconfig:
            self.cpp_info.components["occt_tkservice"].requires.append("fontconfig::fontconfig")
        if self.options.with_ffmpeg:
            self.cpp_info.components["occt_tkservice"].requires.append("ffmpeg::ffmpeg")
        if self.options.with_freeimage:
            self.cpp_info.components["occt_tkservice"].requires.append("freeimage::freeimage")
        if self.options.with_openvr:
            self.cpp_info.components["occt_tkservice"].requires.append("openvr::openvr")
        ### and XwLibs, fontconfig, XmuLibs, dpsLibs?
        if self.settings.os == "Windows":
            self.cpp_info.components["occt_tkservice"].system_libs.extend(["advapi32", "gdi32", "user32", "winmm"])
        elif tools.is_apple_os(self.settings.os):
            self.cpp_info.components["occt_tkservice"].frameworks.extend(["Appkit", "IOKit"])

        ## TKShHealing
        if self.settings.os == "Windows":
            self.cpp_info.components["occt_tkshhealing"].system_libs.append("wsock32")

        ## TKTopAlgo
        if self.options.with_tbb:
            self.cpp_info.components["occt_tktopalgo"].requires.append("tbb::tbb")

        ## TKV3d
        self.cpp_info.components["occt_tkv3d"].requires.extend(["freetype::freetype", "opengl::opengl"])
        if self.options.with_tbb:
            self.cpp_info.components["occt_tkv3d"].requires.append("tbb::tbb")
        ### and XwLibs?
        if self.settings.os == "Windows":
            self.cpp_info.components["occt_tkv3d"].system_libs.extend(["gdi32", "user32"])

        ## TKViewerTest
        self.cpp_info.components["occt_tkviewertest"].requires.extend(["freetype::freetype", "opengl::opengl", "tcl::tcl", "tk::tk"])
        if self.options.with_tbb:
            self.cpp_info.components["occt_tkviewertest"].requires.append("tbb::tbb")
        ### and XwLibs?
        if self.settings.os == "Windows":
            self.cpp_info.components["occt_tkviewertest"].system_libs.extend(["gdi32", "user32"])
        elif tools.is_apple_os(self.settings.os):
            self.cpp_info.components["occt_tkviewertest"].frameworks.extend(["Appkit", "IOKit"])

        # DRAWEXE executable is not created if static build
        if self.options.shared:
            bin_path = os.path.join(self.package_folder, "bin")
            self.output.info("Appending PATH environment variable: {}".format(bin_path))
            self.env_info.PATH.append(bin_path)
