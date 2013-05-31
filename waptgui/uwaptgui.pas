unit uwaptgui;

{$mode objfpc}{$H+}

interface

uses
  Classes, SysUtils, memds, BufDataset, FileUtil, SynHighlighterPython, SynEdit,
  SynMemo, vte_edittree, vte_json, LSControls, Forms,
  Controls, Graphics, Dialogs, ExtCtrls, StdCtrls, ComCtrls, ActnList, Menus,
  EditBtn, AtomPythonEngine, PythonGUIInputOutput, process, fpJson, jsonparser,
  superobject, VirtualTrees;

type

  { TVisWaptGUI }

  TVisWaptGUI = class(TForm)
    ActInstall: TAction;
    ActEditpackage: TAction;
    ActInit: TAction;
    ActEvaluate: TAction;
    ActBuildUpload: TAction;
    ActEditSearch: TAction;
    ActEditRemove: TAction;
    ActEditSavePackage: TAction;
    ActUpgrade: TAction;
    ActUpdate: TAction;
    ActRemove: TAction;
    ActSearchPackage: TAction;
    ActionList1: TActionList;
    BufDataset1: TBufDataset;
    butInitWapt: TButton;
    butRun: TButton;
    butSearchPackages: TButton;
    butSearchPackages1: TButton;
    Button1: TButton;
    Button2: TButton;
    Button3: TButton;
    Button4: TButton;
    Button5: TButton;
    cbShowLog: TCheckBox;
    EdSection: TComboBox;
    Eddescription: TEdit;
    EdSearch1: TEdit;
    EdSourceDir: TEdit;
    EdPackage: TEdit;
    EdVersion: TEdit;
    EdRun: TEdit;
    EdSearch: TEdit;
    Label1: TLabel;
    Label2: TLabel;
    Label3: TLabel;
    Label4: TLabel;
    lstPackages: TListView;
    lstDepends: TListView;
    lstPackages1: TListView;
    Memo1: TMemo;
    MenuItem1: TMenuItem;
    MenuItem2: TMenuItem;
    MenuItem3: TMenuItem;
    MenuItem4: TMenuItem;
    PageControl1: TPageControl;
    Panel1: TPanel;
    Panel2: TPanel;
    Panel3: TPanel;
    Panel4: TPanel;
    Panel5: TPanel;
    Panel6: TPanel;
    Panel7: TPanel;
    Panel8: TPanel;
    Panel9: TPanel;
    PopupMenuPackages: TPopupMenu;
    PopupMenuEditDepends: TPopupMenu;
    PythonEngine1: TAtomPythonEngine;
    PythonGUIInputOutput1: TPythonGUIInputOutput;
    Splitter1: TSplitter;
    Splitter2: TSplitter;
    SynPythonSyn1: TSynPythonSyn;
    TabSheet1: TTabSheet;
    TabSheet2: TTabSheet;
    TabSheet3: TTabSheet;
    TabSheet4: TTabSheet;
    pgEditPackage: TTabSheet;
    pgInventory: TTabSheet;
    testedit: TSynEdit;
    tvjson: TVirtualJSONInspector;
    tvjson1: TVirtualJSONInspector;
    jsonlog: TVirtualJSONInspector;
    VirtualJSONListView1: TVirtualJSONListView;
    procedure ActBuildUploadExecute(Sender: TObject);
    procedure ActEditpackageExecute(Sender: TObject);
    procedure ActEditRemoveExecute(Sender: TObject);
    procedure ActEditSavePackageExecute(Sender: TObject);
    procedure ActEditSearchExecute(Sender: TObject);
    procedure ActEvaluateExecute(Sender: TObject);
    procedure ActInitExecute(Sender: TObject);
    procedure ActInstallExecute(Sender: TObject);
    procedure ActRemoveExecute(Sender: TObject);
    procedure ActSearchPackageExecute(Sender: TObject);
    procedure ActUpdateExecute(Sender: TObject);
    procedure ActUpgradeExecute(Sender: TObject);
    procedure cbShowLogClick(Sender: TObject);
    procedure EdRunKeyPress(Sender: TObject; var Key: char);
    procedure EdSearch1KeyPress(Sender: TObject; var Key: char);
    procedure EdSearchKeyPress(Sender: TObject; var Key: char);
    procedure FormCreate(Sender: TObject);
    procedure FormDestroy(Sender: TObject);
    procedure lstDependsDragDrop(Sender, Source: TObject; X, Y: Integer);
    procedure lstDependsDragOver(Sender, Source: TObject; X, Y: Integer;
      State: TDragState; var Accept: Boolean);
    procedure VirtualJSONListView1Edited(Sender: TBaseVirtualTree;
      Node: PVirtualNode; Column: TColumnIndex);
    procedure VirtualJSONListView1InitNode(Sender: TBaseVirtualTree;
      ParentNode, Node: PVirtualNode; var InitialStates: TVirtualNodeInitStates
      );
    procedure VirtualJSONListView1KeyDown(Sender: TObject; var Key: Word;
      Shift: TShiftState);
    procedure VirtualJSONListView1NewText(Sender: TBaseVirtualTree;
      Node: PVirtualNode; Column: TColumnIndex; const NewText: String);
  private
    { private declarations }
    function RunJSON(expr:UTF8String;jsonView:TVirtualJSONInspector=Nil):ISuperObject;
    procedure EditPackage(PackageEntry:ISuperObject);
  public
    { public declarations }
    jsondata:TJSONData;
    PackageEdited:ISuperObject;
    waptpath:String;
    procedure LoadJson(data:UTF8String);
  end;

var
  VisWaptGUI: TVisWaptGUI;

implementation
uses LCLIntf,soutils,waptcommon;
{$R *.lfm}

{ TVisWaptGUI }
function StrToken(var S: string; Separator: Char): string;
var
  I: SizeInt;
begin
  I := Pos(Separator, S);
  if I <> 0 then
  begin
    Result := Copy(S, 1, I - 1);
    Delete(S, 1, I);
  end
  else
  begin
    Result := S;
    S := '';
  end;
end;

procedure TVisWaptGUI.cbShowLogClick(Sender: TObject);
begin
  if cbShowLog.Checked then
    PythonEngine1.ExecString('logger.setLevel(logging.DEBUG)')
  else
    PythonEngine1.ExecString('logger.setLevel(logging.WARNING)');

end;

procedure TVisWaptGUI.EdRunKeyPress(Sender: TObject; var Key: char);
begin
  if Key=#13 then
    ActEvaluate.Execute;
end;

procedure TVisWaptGUI.EdSearch1KeyPress(Sender: TObject; var Key: char);
begin
  if Key=#13 then
   begin
     EdSearch1.SelectAll;
     ActEditSearch.Execute;
   end;
end;

procedure TVisWaptGUI.EdSearchKeyPress(Sender: TObject; var Key: char);
begin
 if Key=#13 then
  begin
    EdSearch.SelectAll;
    ActSearchPackage.Execute;
  end;

end;

procedure TVisWaptGUI.ActInstallExecute(Sender: TObject);
var
  expr,res:String;
  package:String;
  i:integer;
  N : PVirtualNode;
begin
  if lstPackages.Focused then
  begin
    package := lstPackages.Selected.Caption+' (='+lstPackages.Selected.SubItems[1]+')';
    RunJSON(format('mywapt.install("%s")',[package]),jsonlog);
    ActSearchPackage.Execute;
  end
  else
  begin
    N := VirtualJSONListView1.GetFirstSelected;
    while N<>Nil do
    begin
      package := VirtualJSONListView1.Text[N,0]+' (='+VirtualJSONListView1.Text[N,2]+')';
      RunJSON(format('mywapt.install("%s")',[package]),jsonlog);
      N := VirtualJSONListView1.GetNextSelected(N);
    end;
    ActSearchPackage.Execute;
  end;
end;

procedure TVisWaptGUI.ActEditpackageExecute(Sender: TObject);
var
  expr,res,depends,dep:String;
  package:String;
  result:ISuperObject;
  item : TListItem;
begin
  if lstPackages.Focused then
  begin
    package := lstPackages.Selected.Caption;
    result := RunJSON(format('mywapt.edit_package("%s")',[package]),jsonlog);
    {if DirectoryExists(result.S['target']) then
      OpenDocument(Format('%s\WAPT\control',[result.S['target']]));}
    //EditPackage( );
  end;
end;

procedure TVisWaptGUI.EditPackage(PackageEntry:ISuperObject);
var
  depends,dep:String;
  result:ISuperObject;
  item : TListItem;
begin
  PackageEdited := PackageEntry;
  EdSourceDir.Text:=PackageEdited.S['target'];
  EdPackage.Text:=PackageEdited.S['package'];
  EdVersion.Text:=PackageEdited.S['version'];
  EdDescription.Text:=PackageEdited.S['description'];
  EdSection.Text:=PackageEdited.S['section'];
  lstDepends.Clear;
  depends := PackageEdited.S['depends'];
  while depends<>'' do
  begin
    dep := StrToken(depends,',');
    item := lstDepends.Items.Add;
    item.Caption:=dep;
  end;
end;

procedure TVisWaptGUI.ActEditRemoveExecute(Sender: TObject);
var
  i:integer;
  oldepends,newdepends : ISuperObject;
begin
  oldepends := Split(PackageEdited.S['depends'],',');
  newdepends := TSuperObject.Create(stArray);
  for i:=0 to lstDepends.Items.Count-1 do
    if not lstDepends.Items[i].Selected then
      newdepends.AsArray.Add(lstDepends.Items[i].Caption);
  PackageEdited.S['depends'] := Join(',',newdepends);
  ActEditSavePackage.Execute;
  EditPackage(PackageEdited);
end;

procedure TVisWaptGUI.ActEditSavePackageExecute(Sender: TObject);
var
  Depends:String;
  i:integer;
begin
  Screen.Cursor:=crHourGlass;
  try
    PackageEdited.S['package'] := EdPackage.Text;
    PackageEdited.S['version'] := EdVersion.Text;
    PackageEdited.S['description'] := EdDescription.Text;
    PackageEdited.S['section'] := EdSection.Text;
    Depends:='';
    for i:=0 to lstDepends.Items.Count-1 do
    begin
      if Depends<>'' then
        Depends:=Depends+','+lstDepends.Items[i].Caption
      else
        Depends:=lstDepends.Items[i].Caption;
    end;
    PackageEdited.S['depends'] := depends;
    PythonEngine1.ExecString('p = PackageEntry()');
    PythonEngine1.ExecString(format('p.load_control_from_dict(json.loads(''%s''))',[PackageEdited.AsJson]));
    PythonEngine1.ExecString(format('p.save_control_to_wapt(r''%s'')',[EdSourceDir.Text]));
  finally
    Screen.Cursor:=crDefault;
  end;
end;

procedure TVisWaptGUI.ActEditSearchExecute(Sender: TObject);
var
  expr,res:UTF8String;
  packages,package:ISuperObject;
  item : TListItem;
begin
  lstPackages1.Clear;
  expr := format('mywapt.search("%s".split())',[EdSearch1.Text]);
  packages := RunJSON(expr);
  if packages<>Nil then
  try
    lstPackages1.BeginUpdate;
    if packages.DataType = stArray then
    begin
      for package in packages do
      begin
        item := lstPackages1.Items.Add;
        item.Caption:=package.S['package'];
        item.SubItems.Add(package.S['version']);
        item.SubItems.Add(package.S['description']);
        item.SubItems.Add(package.S['depends']);
      end;
    end;

  finally
    lstPackages1.EndUpdate;
  end;
end;

procedure TVisWaptGUI.ActBuildUploadExecute(Sender: TObject);
var
  expr,res:String;
  package:String;
  result:ISuperObject;
begin
  ActEditSavePackage.Execute;
  result := RunJSON(format('mywapt.build_upload(r"%s")',[EdSourceDir.Text]),jsonlog);

end;

procedure TVisWaptGUI.ActEvaluateExecute(Sender: TObject);
var
  res:String;
  o,sob:ISuperObject;
begin
  Memo1.Clear;
  if cbShowLog.Checked then
  begin
    Memo1.Lines.Add('');
    Memo1.Lines.Add('########## Start of Output of """'+EdRun.Text+'""" : ########');
  end;

  sob := RunJSON(EdRun.Text,jsonlog);
end;

procedure TVisWaptGUI.ActInitExecute(Sender: TObject);
begin
  Memo1.Clear;
  PythonEngine1.ExecString(testedit.Lines.Text);
end;

procedure TVisWaptGUI.ActRemoveExecute(Sender: TObject);
var
  expr,res:String;
  package:String;
begin
  if lstPackages.Focused then
  begin
    package := lstPackages.Selected.Caption;
    expr := format('mywapt.remove("%s")',[package]);
    RunJSON(expr,jsonlog);
    ActSearchPackage.Execute;
  end;
end;

procedure TVisWaptGUI.ActSearchPackageExecute(Sender: TObject);
var
  expr,res:UTF8String;
  packages,package:ISuperObject;
  item : TListItem;
  jsp : TJSONParser;
begin
  lstPackages.Clear;
  expr := format('mywapt.search("%s".split())',[EdSearch.Text]);
  packages := RunJSON(expr);
  if packages<>Nil then
  try
    jsp := TJSONParser.Create(packages.AsJSon);
    VirtualJSONListView1.Data := jsp.Parse;
    VirtualJSONListView1.LoadData;
    VirtualJSONListView1.Header.AutoFitColumns;
    jsp.Free;
    lstPackages.BeginUpdate;
    if packages.DataType = stArray then
    begin
      for package in packages do
      begin
        item := lstPackages.Items.Add;
        item.Caption:=package.S['package'];
        item.SubItems.Add(package.S['status']);
        item.SubItems.Add(package.S['version']);
        item.SubItems.Add(package.S['description']);
        item.SubItems.Add(package.S['depends']);
        if package.S['status'][1] in  ['I','U'] then
          item.Checked:=True;
      end;
    end;

  finally
    lstPackages.EndUpdate;
  end;
end;

procedure TVisWaptGUI.ActUpdateExecute(Sender: TObject);
var
  expr,res:UTF8String;
  sores:ISuperObject;

begin
  expr := format('mywapt.update()',[]);
  RunJSON(expr,jsonlog);
  tvjson1.RootData := jsonlog.RootData;

end;

procedure TVisWaptGUI.ActUpgradeExecute(Sender: TObject);
begin
  RunJSON('mywapt.upgrade()',jsonlog);
  tvjson1.RootData := jsonlog.RootData;
end;


procedure TVisWaptGUI.FormCreate(Sender: TObject);
begin
  with pythonEngine1 do
  begin
    DllName := 'python27.dll';
    RegVersion := '2.7';
    UseLastKnownVersion := False;
    LoadDLL;
    Py_SetProgramName(PAnsiChar(ParamStr(0)));
  end;
  butInitWapt.Click;

  lstPackages.Clear;
  Memo1.Clear;

  lstDepends.Clear;
  lstPackages1.Clear;

  waptpath := ExtractFileDir(paramstr(0));

end;

procedure TVisWaptGUI.FormDestroy(Sender: TObject);
begin
  if Assigned(jsondata) then
    FreeAndNil(jsondata);
end;

procedure TVisWaptGUI.lstDependsDragDrop(Sender, Source: TObject; X, Y: Integer
  );
var
  i:integer;
  li : TListItem;
begin
  for i:=0 to lstPackages1.Items.Count-1 do
  begin
    if lstPackages1.Items[i].Selected then
    begin
      li := lstDepends.Items.FindCaption(0,lstPackages1.Items[i].Caption,False,False,False);
      if li=Nil then
      begin
        li := lstDepends.Items.Add;
        li.Caption:=lstPackages1.Items[i].Caption;
        li.SubItems.Append(lstPackages1.Items[i].SubItems[0]);
        li.SubItems.Append(lstPackages1.Items[i].SubItems[1]);
        li.SubItems.Append(lstPackages1.Items[i].SubItems[2]);
      end;
      li.Selected:=True;
    end;
  end;
end;

procedure TVisWaptGUI.lstDependsDragOver(Sender, Source: TObject; X,
  Y: Integer; State: TDragState; var Accept: Boolean);
begin
  Accept := Source = lstPackages1;
end;

procedure TVisWaptGUI.VirtualJSONListView1Edited(Sender: TBaseVirtualTree;
  Node: PVirtualNode; Column: TColumnIndex);
begin

end;

procedure TVisWaptGUI.VirtualJSONListView1InitNode(Sender: TBaseVirtualTree;
  ParentNode, Node: PVirtualNode; var InitialStates: TVirtualNodeInitStates);
begin
  InitialStates:=InitialStates + [vsMultiline];
end;

procedure TVisWaptGUI.VirtualJSONListView1KeyDown(Sender: TObject;
  var Key: Word; Shift: TShiftState);
begin
  //VirtualJSONListView1.EditNode(VirtualJSONListView1.FocusedNode,VirtualJSONListView1.FocusedColumn);
end;

procedure TVisWaptGUI.VirtualJSONListView1NewText(Sender: TBaseVirtualTree;
  Node: PVirtualNode; Column: TColumnIndex; const NewText: String);
begin

end;

procedure TVisWaptGUI.LoadJson(data: UTF8String);
var
  P:TJSONParser;
begin
  P:=TJSONParser.Create(Data,True);
  try
    if jsondata<>Nil then
      FreeAndNil(jsondata);
    jsondata := P.Parse;
  finally
      FreeAndNil(P);
  end;
end;

function TVisWAPTGui.RunJSON(expr:UTF8String;jsonView:TVirtualJSONInspector=Nil):ISuperObject;
var
  res:UTF8String;
begin
  if Assigned(jsonView) then
    jsonView.Clear;

  Memo1.Clear;
  if cbShowLog.Checked then
    Memo1.Lines.Append(expr);
  res := PythonEngine1.EvalStringAsStr(format('jsondump(%s)',[expr]));
  if cbShowLog.Checked then
    Memo1.Lines.Append(res);
  result := SO( UTF8Decode(res) );

  if Assigned(jsonView) then
  begin
    LoadJson(res);
    jsonView.RootData := jsondata;
  end;

end;

end.

