#!/usr/bin/env python3
"""
commands.py - Générateur de commandes Voltronic
================================================

Génère les commandes P... pour modifier les paramètres des onduleurs
"""


class VoltronicCommands:
    """
    Générateur de commandes Voltronic pour modification des paramètres
    
    Toutes les commandes retournent une string au format Voltronic
    qui sera ensuite envoyée via le port série avec CRC
    """
    
    # ============= TENSIONS BATTERIE =============
    
    @staticmethod
    def set_battery_charge_voltage(voltage: float) -> str:
        """
        PBT - Battery Charge Voltage (Bulk voltage)
        
        Args:
            voltage: Tension en Volts (50.0 - 60.0)
            
        Returns:
            Commande formatée (ex: "PBT58.4")
            
        Exemple:
            >>> VoltronicCommands.set_battery_charge_voltage(58.4)
            'PBT58.4'
        """
        if not 50.0 <= voltage <= 60.0:
            raise ValueError(f"Tension invalide: {voltage}V (doit être entre 50-60V)")
        return f"PBT{voltage:.1f}"
    
    @staticmethod
    def set_battery_float_voltage(voltage: float) -> str:
        """
        PBFT - Battery Float Charge Voltage
        
        Args:
            voltage: Tension en Volts (50.0 - 60.0)
            
        Returns:
            Commande formatée (ex: "PBFT54.4")
        """
        if not 50.0 <= voltage <= 60.0:
            raise ValueError(f"Tension invalide: {voltage}V (doit être entre 50-60V)")
        return f"PBFT{voltage:.1f}"
    
    @staticmethod
    def set_battery_cutoff_voltage(voltage: float) -> str:
        """
        PSDV - Battery Cut-off Voltage (shutdown)
        
        Args:
            voltage: Tension en Volts (40.0 - 50.0)
            
        Returns:
            Commande formatée (ex: "PSDV44.8")
        """
        if not 40.0 <= voltage <= 50.0:
            raise ValueError(f"Tension invalide: {voltage}V (doit être entre 40-50V)")
        return f"PSDV{voltage:.1f}"
    
    @staticmethod
    def set_battery_recharge_voltage(voltage: float) -> str:
        """
        PBR - Battery Re-charge Voltage (Back to grid/discharge)
        
        Args:
            voltage: Tension en Volts (45.0 - 55.0)
            
        Returns:
            Commande formatée (ex: "PBR49.0")
        """
        if not 45.0 <= voltage <= 55.0:
            raise ValueError(f"Tension invalide: {voltage}V (doit être entre 45-55V)")
        return f"PBR{voltage:.1f}"
    
    # ============= COURANTS DE CHARGE =============
    
    @staticmethod
    def set_max_charge_current(current: int) -> str:
        """
        MCHGC - Max Charge Current (total)
        
        Args:
            current: Courant en Ampères (0 - 200)
            
        Returns:
            Commande formatée (ex: "MCHGC060")
        """
        if not 0 <= current <= 200:
            raise ValueError(f"Courant invalide: {current}A (doit être entre 0-200A)")
        return f"MCHGC{current:03d}"
    
    @staticmethod
    def set_max_ac_charge_current(current: int) -> str:
        """
        MUCHGC - Max AC Charge Current (secteur uniquement)
        
        Args:
            current: Courant en Ampères (0 - 100)
            
        Returns:
            Commande formatée (ex: "MUCHGC020")
        """
        if not 0 <= current <= 100:
            raise ValueError(f"Courant invalide: {current}A (doit être entre 0-100A)")
        return f"MUCHGC{current:03d}"
    
    # ============= PRIORITÉS =============
    
    @staticmethod
    def set_output_source_priority(priority: int) -> str:
        """
        POP - Output Source Priority
        
        Args:
            priority: 
                0 = Utility first (Secteur prioritaire)
                1 = Solar first (Solaire prioritaire)
                2 = SBU first (Solar-Battery-Utility)
                
        Returns:
            Commande formatée (ex: "POP02")
        """
        if priority not in [0, 1, 2]:
            raise ValueError(f"Priorité invalide: {priority} (doit être 0, 1 ou 2)")
        return f"POP{priority:02d}"
    
    @staticmethod
    def set_charger_source_priority(priority: int) -> str:
        """
        PCP - Charger Source Priority
        
        Args:
            priority:
                0 = Utility first (Secteur prioritaire)
                1 = Solar first (Solaire prioritaire)
                2 = Solar + Utility (Les deux)
                3 = Solar only (Solaire uniquement)
                
        Returns:
            Commande formatée (ex: "PCP01")
        """
        if priority not in [0, 1, 2, 3]:
            raise ValueError(f"Priorité invalide: {priority} (doit être 0, 1, 2 ou 3)")
        return f"PCP{priority:02d}"
    
    # ============= MODES DE SORTIE =============
    
    @staticmethod
    def set_output_mode(mode: int) -> str:
        """
        POM - Output Mode
        
        Args:
            mode:
                0 = Single machine output
                1 = Parallel output
                2 = Phase 1 of 3 phase output
                3 = Phase 2 of 3 phase output
                4 = Phase 3 of 3 phase output
                
        Returns:
            Commande formatée (ex: "POM02")
        """
        if not 0 <= mode <= 4:
            raise ValueError(f"Mode invalide: {mode} (doit être entre 0-4)")
        return f"POM{mode:02d}"
    
    # ============= UTILITAIRES =============
    
    @staticmethod
    def get_command_description(command: str) -> str:
        """
        Obtient la description d'une commande
        
        Args:
            command: Commande (ex: "PBT58.4")
            
        Returns:
            Description lisible
        """
        cmd_type = command[:3] if len(command) >= 3 else command
        
        descriptions = {
            "PBT": "Battery Charge Voltage (Bulk)",
            "PBF": "Battery Float Voltage",
            "PSD": "Battery Cut-off Voltage",
            "PBR": "Battery Recharge Voltage",
            "MCH": "Max Charge Current",
            "MUC": "Max AC Charge Current",
            "POP": "Output Source Priority",
            "PCP": "Charger Source Priority",
            "POM": "Output Mode",
        }
        
        return descriptions.get(cmd_type, "Commande inconnue")
    
    @staticmethod
    def validate_all_parameters(params: dict) -> dict:
        """
        Valide un ensemble de paramètres
        
        Args:
            params: Dictionnaire de paramètres à valider
            
        Returns:
            Dictionnaire {param: (valid, message)}
        """
        results = {}
        
        if "battery_voltage" in params:
            v = params["battery_voltage"]
            results["battery_voltage"] = (50.0 <= v <= 60.0, 
                                         f"{'✅' if 50.0 <= v <= 60.0 else '❌'} {v}V")
        
        if "float_voltage" in params:
            v = params["float_voltage"]
            results["float_voltage"] = (50.0 <= v <= 60.0,
                                       f"{'✅' if 50.0 <= v <= 60.0 else '❌'} {v}V")
        
        if "cutoff_voltage" in params:
            v = params["cutoff_voltage"]
            results["cutoff_voltage"] = (40.0 <= v <= 50.0,
                                        f"{'✅' if 40.0 <= v <= 50.0 else '❌'} {v}V")
        
        if "recharge_voltage" in params:
            v = params["recharge_voltage"]
            results["recharge_voltage"] = (45.0 <= v <= 55.0,
                                          f"{'✅' if 45.0 <= v <= 55.0 else '❌'} {v}V")
        
        if "max_charge_current" in params:
            c = params["max_charge_current"]
            results["max_charge_current"] = (0 <= c <= 200,
                                            f"{'✅' if 0 <= c <= 200 else '❌'} {c}A")
        
        if "max_ac_charge_current" in params:
            c = params["max_ac_charge_current"]
            results["max_ac_charge_current"] = (0 <= c <= 100,
                                               f"{'✅' if 0 <= c <= 100 else '❌'} {c}A")
        
        return results


# ============= PRESETS POUR CONFIGURATIONS COURANTES =============

class VoltronicPresets:
    """
    Configurations pré-définies pour différents types de batteries
    """
    
    @staticmethod
    def lifepo4_16s_conservative():
        """Configuration conservatrice pour LiFePO4 16S"""
        return {
            "battery_voltage": 58.4,     # 3.65V par cellule
            "float_voltage": 54.4,       # 3.40V par cellule
            "cutoff_voltage": 44.8,      # 2.80V par cellule
            "recharge_voltage": 50.4,    # 3.15V par cellule (35% SOC)
            "description": "LiFePO4 16S - Conservateur (longue durée de vie)"
        }
    
    @staticmethod
    def lifepo4_16s_balanced():
        """Configuration équilibrée pour LiFePO4 16S"""
        return {
            "battery_voltage": 58.4,     # 3.65V par cellule
            "float_voltage": 54.4,       # 3.40V par cellule
            "cutoff_voltage": 44.8,      # 2.80V par cellule
            "recharge_voltage": 49.0,    # 3.06V par cellule (28% SOC)
            "description": "LiFePO4 16S - Équilibré (bon compromis)"
        }
    
    @staticmethod
    def lifepo4_16s_performance():
        """Configuration performance pour LiFePO4 16S"""
        return {
            "battery_voltage": 58.4,     # 3.65V par cellule
            "float_voltage": 54.4,       # 3.40V par cellule
            "cutoff_voltage": 44.8,      # 2.80V par cellule
            "recharge_voltage": 48.0,    # 3.00V par cellule (20% SOC)
            "description": "LiFePO4 16S - Performance (capacité max)"
        }
    
    @staticmethod
    def get_preset_commands(preset_name: str) -> dict:
        """
        Obtient les commandes pour un preset donné
        
        Args:
            preset_name: Nom du preset
            
        Returns:
            Dictionnaire {param: command}
        """
        presets = {
            "conservative": VoltronicPresets.lifepo4_16s_conservative(),
            "balanced": VoltronicPresets.lifepo4_16s_balanced(),
            "performance": VoltronicPresets.lifepo4_16s_performance(),
        }
        
        if preset_name not in presets:
            raise ValueError(f"Preset inconnu: {preset_name}")
        
        config = presets[preset_name]
        commands = {}
        
        if "battery_voltage" in config:
            commands["battery_voltage"] = VoltronicCommands.set_battery_charge_voltage(config["battery_voltage"])
        if "float_voltage" in config:
            commands["float_voltage"] = VoltronicCommands.set_battery_float_voltage(config["float_voltage"])
        if "cutoff_voltage" in config:
            commands["cutoff_voltage"] = VoltronicCommands.set_battery_cutoff_voltage(config["cutoff_voltage"])
        if "recharge_voltage" in config:
            commands["recharge_voltage"] = VoltronicCommands.set_battery_recharge_voltage(config["recharge_voltage"])
        
        return commands
