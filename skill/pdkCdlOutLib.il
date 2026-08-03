;=============================================================================
; pdkCdlOutLib.il
;   pdkCdlOutLib(lib) - CDL netlist every schematic view in a library
;   runCDLout(lib cell) - run si -batch for one cell
;   siEnvPrep(lib cell) - write ./si.env for one cell
;=============================================================================
procedure(pdkCdlOutLib(lib)
    libId=ddGetObj(lib)
    foreach(cellId libId~>cells
        foreach(viewId cellId~>views
            ;if(rexMatchp("schematic" viewId~>name) || rexMatchp("layout" viewId~>name) then
            if(rexMatchp("schematic" viewId~>name) then
                printf("Cdl Out: %s %s %s in ./pdkCdlOutLib/%s/%s/%s.cdl\n" libId~>name cellId~>name viewId~>name libId~>name cellId~>name cellId~>name)
                ; change cell, wire and trigger
                cell=cellId~>name
                runCDLout(lib cell)
                ;system(strcat("mkdir -p " lib "/" cell))
                ;system(strcat("mv " cell ".cdl ./" lib "/" cell "/"))
                system(sprintf(nil "mkdir -p pdkCdlOutLib/%L/%L/" lib cell))
                system(sprintf(nil "rm -rf pdkCdlOutLib/%L/%L/%L.cdl" lib cell cell))
                system(sprintf(nil "mv %L.cdl pdkCdlOutLib/%L/%L/" cell lib cell))
            );if
        );foreach
    );foreach
)
procedure(runCDLout(lib cell)
    prog(
        (id)
        ;;remove lock file
        when(isFile(strcat(getWorkingDir() "/.running"))
            system(sprintf(nil "rm %s/.running" getWorkingDir()) );
        );
        ;;create si.env file
        siEnvPrep(lib cell);
        ;id = ipcBeginProcess("si -batch -command netlist");
        ;ipcWait(id);
        system("si -batch -command netlist > si.log");
    );end prog
);irunCDLout

procedure(siEnvPrep(lib cell)
    prog(
        (outFile runDir)
        runDir = strcat(getWorkingDir() "/act_generator/cdl");
        outFile = outfile("./si.env" "w");
        fprintf(outFile
            sprintf(nil "
                simLibName = \"%s\" \n
                simCellName = \"%s\" \n
                simViewName = \"schematic\" \n
                simSimulator = \"auCdl\" \n
                simNotIncremental = nil\n
                simReNetlistAll = 't\n
                simViewList = '(\"auCdl\" \"schematic\" \"symbol\")\n
                simStopList = '(\"auCdl\")\n
                simNetlistHier = t \n
                hnlNetlistFileName = \"%s\" \n
                resistorModel = \"\"\n
                shortRES = 2000.0 \n
                preserveRES = 't \n
                checkRESVAL = 't \n
                checkRESSIZE = 'nil \n
                preserveCAP = 't \n
                checkCAPVAL = 't \n
                checkCAPAREA = 'nil \n
                preserveDIO = 't \n
                checkDIOAREA = 't \n
                checkDIOPERI = 't \n
                checkCAPPERI = 'nil \n
                simPrintInhConnAttributes = 'nil \n
                checkScale = \"meter\" \n
                checkLDD = 'nil \n
                pinMAP = 'nil \n
                preserveBangInNetlist = 'nil \n
                shrinkFACTOR = 0.0 \n
                globalPowerSig = \"\" \n
                globalGndSig = \"\" \n
                displayPININFO = 't \n
                preserveALL = 't \n
                setEQUIV = \"\" \n
                incFILE = \"/datacenter/techLibs/tsmc/T22N/tools/pdk_sirius/T22N/iPDK.20200916/tsmcN22/../Calibre/lvs/source.added\" \n
                auCdlDefNetlistProc = \"ansCdlSubcktCall\"
                "
                lib cell strcat(cell ".cdl")
            );end sprintf
        );end fprintf
        close(outFile);
    );prog
);proc
