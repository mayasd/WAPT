unit uvishostsupgrade;

{$mode objfpc}{$H+}

interface

uses
  Classes, SysUtils, FileUtil, Forms, Controls, Graphics, Dialogs, StdCtrls,
  ActnList, ExtCtrls, Buttons, sogrid,superobject,VirtualTrees, DefaultTranslator;

type

  { TVisHostsUpgrade }

  TVisHostsUpgrade = class(TForm)
    ActStop: TAction;
    ActUpgrade: TAction;
    ActionList1: TActionList;
    BitBtn2: TBitBtn;
    Button1: TButton;
    Button5: TButton;
    Panel4: TPanel;
    ProgressGrid: TSOGrid;
    procedure ActStopExecute(Sender: TObject);
    procedure ActUpgradeExecute(Sender: TObject);
    procedure FormCreate(Sender: TObject);
    procedure ProgressGridInitNode(Sender: TBaseVirtualTree; ParentNode,
      Node: PVirtualNode; var InitialStates: TVirtualNodeInitStates);
    procedure ProgressGridMeasureItem(Sender: TBaseVirtualTree;
      TargetCanvas: TCanvas; Node: PVirtualNode; var NodeHeight: Integer);
  private
    Faction: String;
    Fhosts: ISuperObject;
    Stopped : Boolean;
    procedure Setaction(AValue: String);
    procedure Sethosts(AValue: ISuperObject);
    { private declarations }
  public
    { public declarations }
    property action:String read Faction write Setaction;
    property hosts:ISuperObject read Fhosts write Sethosts;
  end;

var
  VisHostsUpgrade: TVisHostsUpgrade;

implementation

{$R *.lfm}
uses tiscommon,waptcommon,IdHTTP;

{ TVisHostsUpgrade }

procedure TVisHostsUpgrade.ActUpgradeExecute(Sender: TObject);
var
  ips,res,host,ip:ISuperObject;
  lasterror:Utf8String;
begin
  Stopped := False;
  for host in ProgressGrid.Data do
  begin
    if uppercase(host.S['status'])<>'OK' then
    begin
      host.S['status'] := '';
      host.S['message'] := '';
    end;
  end;
  ProgressGrid.Refresh;

  for host in ProgressGrid.Data do
  begin
    if Stopped then Break;
    if uppercase(host.S['status']) = 'OK' then
      Continue;

    host.S['status'] := 'STARTED';
    ProgressGrid.InvalidateFordata(host);
    Application.ProcessMessages;
    try
      try
        res := WAPTServerJsonGet('%s?uuid=%s',[action,host.S['uuid']]);
        // new behaviour
        if (res<>Nil) and res.AsObject.Exists('success') then
        begin
          if res.AsObject.Exists('msg') then
            host['message'] := res['msg'];
          if  res.B['success'] then
            host.S['status'] := 'OK'
          else
            host.S['status'] := 'ERROR';
        end
        else
          host.S['status'] := 'BAD ANSWER';
      except
        on E:EIdHTTPProtocolException do
          lasterror := E.ErrorMessage;
      end;
      ProgressGrid.InvalidateFordata(host);
      Application.ProcessMessages;
    except
      on E:Exception do
      begin
        host.S['status'] := 'ERROR';
        host.S['message'] := host.S['message']+' '+e.Message;
        ProgressGrid.InvalidateFordata(host);
        Application.ProcessMessages;
      end;
    end;
  end;
end;

procedure TVisHostsUpgrade.FormCreate(Sender: TObject);
begin
  Action := 'upgrade_host';
end;

procedure TVisHostsUpgrade.ProgressGridInitNode(Sender: TBaseVirtualTree;
  ParentNode, Node: PVirtualNode; var InitialStates: TVirtualNodeInitStates);
begin
  InitialStates := InitialStates + [ivsMultiline];
end;

procedure TVisHostsUpgrade.ProgressGridMeasureItem(Sender: TBaseVirtualTree;
  TargetCanvas: TCanvas; Node: PVirtualNode; var NodeHeight: Integer);
begin
  if Sender.MultiLine[Node] then
    NodeHeight := ProgressGrid.ComputeNodeHeight(TargetCanvas, Node, 3);
  if NodeHeight < ProgressGrid.DefaultNodeHeight then
    NodeHeight:=ProgressGrid.DefaultNodeHeight;
end;

procedure TVisHostsUpgrade.ActStopExecute(Sender: TObject);
begin
  Stopped := True;
end;

procedure TVisHostsUpgrade.Sethosts(AValue: ISuperObject);
var
  data : ISuperObject;
begin
  if Fhosts=AValue then Exit;
  FHosts := AValue;
  if FHosts<>Nil then
    data := FHosts.Clone
  else
    data := Nil;
  ProgressGrid.Data := data;
end;

procedure TVisHostsUpgrade.Setaction(AValue: String);
begin
  if Faction=AValue then Exit;
  Faction:=AValue;
end;

end.

